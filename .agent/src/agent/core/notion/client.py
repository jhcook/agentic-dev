
import logging
import urllib.request
import urllib.error
import json
from typing import Optional, Dict, Any, List

from agent.core.net_utils import check_ssl_error

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

    def _request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}/{endpoint}"
        data = None
        if payload:
            data = json.dumps(payload).encode("utf-8")
        
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        
        try:
            with urllib.request.urlopen(req) as res:
                if res.getcode() == 200:
                    resp_body = res.read().decode("utf-8")
                    return json.loads(resp_body)
                else:
                    logger.error(f"Notion API Error {res.getcode()}: {res.read().decode('utf-8')}")
                    raise Exception(f"Notion API Error {res.getcode()}")
        except Exception as e:
            ssl_msg = check_ssl_error(e, url="api.notion.com")
            if ssl_msg:
                # SSL Error is fatal and specific
                logger.error(ssl_msg)
                raise Exception(ssl_msg) from e
            elif isinstance(e, urllib.error.HTTPError):
                 error_body = e.read().decode('utf-8')
                 logger.error(f"HTTP Error {e.code}: {e.reason}")
                 logger.error(f"Response Body: {error_body}")
                 raise e
            else:
                 raise e

    def query_database(self, database_id: str, filter: Optional[Dict[str, Any]] = None, sorts: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, Any]]:
        """
        Queries a Notion database.
        """
        # Ensure database_id is just the UUID if a full URL was passed? 
        # For now assume calling code handles ID extraction or simple ID.
        
        payload: Dict[str, Any] = {}
        if filter:
            payload["filter"] = filter
        if sorts:
            payload["sorts"] = sorts

        # Query endpoint is POST
        data = self._request("POST", f"databases/{database_id}/query", payload)
        return data.get("results", [])

    def update_page_properties(self, page_id: str, properties: Dict[str, Any]) -> None:
        """
        Updates properties of a Notion page.
        """
        payload = {"properties": properties}
        self._request("PATCH", f"pages/{page_id}", payload)

    def get_page(self, page_id: str) -> Dict[str, Any]:
         """Retrieves a Notion page."""
         return self._request("GET", f"pages/{page_id}")

    def create_comment(self, page_id: str, comment_text: str) -> None:
        """Creates a comment on a Notion page."""
        payload = {
            "parent": {"page_id": page_id},
            "rich_text": [{"type": "text", "text": {"content": comment_text}}]
        }
        self._request("POST", "comments", payload)

    def retrieve_comments(self, page_id: str) -> List[Dict[str, Any]]:
      """Retrieves comments from a Notion page."""
      data = self._request("GET", f"comments?block_id={page_id}")
      return data.get("results", [])
