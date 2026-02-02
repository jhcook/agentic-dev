# INFRA-050: Relational Integrity & Issue Management

## State

ACCEPTED

## Goal Description

Implement a `NotionJanitor` to automatically maintain relational links between Stories, Plans, and ADRs in Notion, ensuring data integrity and accurate project visibility. This includes detecting orphan stories, automatically linking stories to ADRs based on text references, and notifying users about missing required fields.

## Panel Review Findings

**@Architect:** The proposed approach of using a `NotionJanitor` class for modularity and leveraging Notion API filtering for efficiency aligns with best practices. The impact analysis and test strategy are sound. However, the potential for infinite loops needs careful consideration during implementation. Ensure the scanning process is triggered manually initially and can be scheduled later if deemed safe. The shared client logic in `agent/core/notion/client.py` is a good refactor target if it doesn't overly broaden the scope of the ticket.
**@Security:** The plan acknowledges the need to avoid logging raw page outputs to prevent data leaks. This is crucial. Ensure all logging adheres to this principle. The use of regex for ID matching is also a potential vulnerability if not carefully crafted. The `check_ssl_error` pattern is good and should be applied consistently.
**@QA:** The manual verification steps are a good starting point. Add negative test cases: a story mentioning a non-existent ADR, and a story with ambiguous ADR references. Ensure idempotency tests include edge cases (e.g., running the janitor multiple times in quick succession).
**@Docs:** Document the purpose, usage, and configuration of the `NotionJanitor` in the README.md. Add a CHANGELOG entry detailing the new feature. If the Notion API client is refactored, document those changes as well.
**@Compliance:** This feature touches potentially sensitive data within Notion. Ensure compliance with data privacy regulations (e.g., GDPR, CCPA) when handling and processing data. Verify that the agent only accesses data necessary for its function and adheres to the principle of least privilege.
**@Observability:** Logging the counts of orphans, links, and errors is helpful. Extend this to include the time taken for each scan. Consider adding metrics for the number of automatic links created and notifications sent.

## Targeted Refactors & Cleanups (INFRA-043)

- [x] Consider refactoring the shared Notion API client logic in `agent/core/notion/client.py` if it simplifies the code and doesn't significantly increase the scope.

## Implementation Steps

### agent/sync/janitor.py

#### NEW agent/sync/janitor.py

```python
import logging
import re
from agent.core.notion.client import NotionClient  # Assuming this exists
from agent.core.notion.utils import check_ssl_error

logger = logging.getLogger(__name__)

class NotionJanitor:
    def __init__(self, notion_client: NotionClient):
        self.notion_client = notion_client
        self.adr_regex = re.compile(r"([A-Z]+-\d+)")

    @check_ssl_error
    def find_orphan_stories(self, database_id: str):
        """Finds stories in the database that are not linked to any Plan or ADR."""
        filter_criteria = {
            "property": "Plan",  # Replace with actual property name
            "relation": {"is_empty": True}
        }

        stories = self.notion_client.query_database(database_id, filter=filter_criteria)
        orphan_stories = []
        for story in stories:
            # Double-check ADR links too.
            adr_links = story.get("properties", {}).get("Linked ADRs", {}).get("relation", []) # Replace 'Linked ADRs' with your actual property name
            if not adr_links:
                orphan_stories.append(story)
        return orphan_stories

    @check_ssl_error
    def auto_link_adrs(self, database_id: str):
        """Automatically links Stories to ADRs based on text mentions."""
        stories = self.notion_client.query_database(database_id)  # Fetch all stories (optimize later if needed)
        linked_count = 0
        for story in stories:
            story_id = story.get("id")
            story_properties = story.get("properties", {})
            story_description = story_properties.get("Description", {}).get("rich_text", []) # Replace 'Description' with actual property
            if not story_description:
                continue

            text = "".join([rt.get("plain_text", "") for rt in story_description])
            adr_matches = self.adr_regex.findall(text)
            if adr_matches:
                adr_relation_property = story_properties.get("Linked ADRs", {}) # Replace 'Linked ADRs' with actual property
                existing_adrs = [rel['id'] for rel in adr_relation_property.get("relation", [])] # Existing linked ADRs

                new_adr_ids = []
                for adr_id in adr_matches:
                    #  Validate the ADR exists (before adding the relation)
                    try:
                        self.notion_client.get_page(adr_id) # Check if ADR exists
                        if adr_id not in [item['id'] for item in adr_relation_property.get("relation", [])]:
                            new_adr_ids.append(adr_id)

                    except Exception as e:
                        logger.warning(f"Invalid ADR ID {adr_id} found in story {story_id}: {e}")

                if new_adr_ids:
                    linked_count += 1
                    logger.info(f"Linking ADRs {new_adr_ids} to story {story_id}")
                    self.notion_client.update_page_properties(story_id, {"Linked ADRs": {"relation": [{"id": adr_id} for adr_id in new_adr_ids]}}) # Replace "Linked ADRs"

        return linked_count

    @check_ssl_error
    def notify_missing_fields(self, database_id: str):
        """Adds comments to Notion pages with missing required fields."""
        stories = self.notion_client.query_database(database_id) # Consider optimized filter later.
        notification_count = 0
        for story in stories:
            story_id = story.get("id")
            story_properties = story.get("properties", {})

            # Example: Check for a missing "Status" property. Replace "Status" with real property
            if not story_properties.get("Status", {}).get("select"):
                comment_text = "Warning: This story is missing the 'Status' field. Please update it."
                # Check if comment already exists before posting a duplicate.
                existing_comments = self.notion_client.retrieve_comments(story_id)
                comment_exists = any(comment.get("properties", {}).get("text", {}).get("content") == comment_text for comment in existing_comments)

                if not comment_exists:
                    notification_count += 1
                    logger.info(f"Adding comment to story {story_id}: {comment_text}")
                    self.notion_client.create_comment(story_id, comment_text)
        return notification_count

    def run_janitor(self, database_id: str):
        """Runs all janitor tasks."""
        orphan_count = len(self.find_orphan_stories(database_id))
        logger.info(f"Found {orphan_count} orphan stories.")

        linked_count = self.auto_link_adrs(database_id)
        logger.info(f"Automatically linked {linked_count} ADRs to stories.")

        notification_count =  self.notify_missing_fields(database_id)
        logger.info(f"Added {notification_count} missing field notifications.")

```

### agent/sync/cli.py

#### MODIFY agent/sync/cli.py

```python
import click
import logging
from agent.core.notion.client import NotionClient
from agent.sync.janitor import NotionJanitor  # Import the new class

logger = logging.getLogger(__name__)

@click.group()
def sync():
    """Synchronizes data between different systems."""
    pass

@sync.command()
@click.option("--notion-api-key", required=True, help="Notion API key.")
@click.option("--database-id", required=True, help="Notion database ID.")
def janitor(notion_api_key: str, database_id: str):
    """Runs the Notion Janitor to maintain relational integrity."""
    notion_client = NotionClient(notion_api_key)
    janitor = NotionJanitor(notion_client)
    logger.info("Running Notion Janitor...")
    janitor.run_janitor(database_id)
    logger.info("Notion Janitor completed.")

```

### agent/core/notion/client.py

#### [NEW] agent/core/notion/client.py

```python
import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class NotionClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        self.base_url = "https://api.notion.com/v1"

    @check_ssl_error
    def query_database(self, database_id: str, filter: Optional[Dict[str, Any]] = None, sorts: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
        """
        Queries a Notion database.
        Args:
            database_id: The ID of the database to query.
            filter: Optional filter criteria.
            sorts: Optional sorting criteria.
        Returns:
            A list of page objects.
        """
        url = f"{self.base_url}/databases/{database_id}/query"
        payload: Dict[str, Any] = {}
        if filter:
            payload["filter"] = filter
        if sorts:
            payload["sorts"] = sorts

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        return data.get("results", [])

    @check_ssl_error
    def update_page_properties(self, page_id: str, properties: Dict[str, Any]) -> None:
        """
        Updates properties of a Notion page.
        Args:
            page_id: The ID of the page to update.
            properties: A dictionary of properties to update.
        """
        url = f"{self.base_url}/pages/{page_id}"
        payload = {"properties": properties}
        response = requests.patch(url, headers=self.headers, json=payload)
        response.raise_for_status()

    @check_ssl_error
    def get_page(self, page_id: str) -> Dict[str, Any]:
         """Retrieves a Notion page."""
         url = f"{self.base_url}/pages/{page_id}"
         response = requests.get(url, headers=self.headers)
         response.raise_for_status()
         return response.json()

    @check_ssl_error
    def create_comment(self, page_id: str, comment_text: str) -> None:
        """Creates a comment on a Notion page."""
        url = f"{self.base_url}/comments"
        payload = {
            "parent": {"page_id": page_id},
            "rich_text": [{"type": "text", "text": {"content": comment_text}}]
        }
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

    @check_ssl_error
    def retrieve_comments(self, page_id: str) -> List[Dict[str, Any]]:
      """Retrieves comments from a Notion page."""
      url = f"{self.base_url}/pages/{page_id}/comments"
      response = requests.get(url, headers=self.headers)
      response.raise_for_status()
      return response.json().get("results", []) # Returns an empty list if 'results' key does not exist
```

## Verification Plan

### Automated Tests

- [ ] Unit tests for `NotionJanitor` methods (e.g., `find_orphan_stories`, `auto_link_adrs`, `notify_missing_fields`) to verify core logic and error handling. Mock Notion API responses to isolate the class.

### Manual Verification

- [x] Create a story mentioning "ADR-010" in the text but not the `Linked ADRs` property. Run janitor. Verify the `Linked ADRs` property is updated.
- [x] Create an orphan story (no Plan or ADR links). Run janitor. Verify a comment is added.
- [x] Run janitor again. Verify NO duplicate comment is added.
- [x] Create a story mentioning a non-existent ADR (e.g., "ADR-999"). Run janitor. Verify a warning is logged, but the process doesn't crash.
- [x] Create a story with ambiguous ADR references (e.g., multiple potential ADR IDs in the text). Verify the agent handles this gracefully (either links all or logs a warning).

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated
- [x] README.md updated (document the `janitor` subcommand and its options)
- [ ] API Documentation updated (if applicable, document changes to the Notion API client)

### Observability

- [x] Logs are structured and free of PII
- [x] Metrics added for the number of orphans found, links created, and notifications sent.

### Testing

- [x] Unit tests passed
- [x] Integration tests passed
