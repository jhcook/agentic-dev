# Story: Standardize SSL Error Handling

## State

COMMITTED

## Problem Statement

The codebase currently handles SSL errors inconsistently across different modules (`notion_schema_manager.py`, `download_models.py`, `vad.py`, `service.py`).
Users behind corporate proxies often encounter generic connection failures without clear instructions.
Recent fixes in Notion integration introduced a specific error message for `CERTIFICATE_VERIFY_FAILED`, but this pattern needs to be applied globally to ensure a uniform user experience.

## User Story

**As a** developer working behind a corporate proxy
**I want** to see a consistent, actionable error message when SSL verification fails anywhere in the agent
**So that** I know exactly how to configure my environment (whitelist/certificate) to resolve the issue.

## Acceptance Criteria

- [ ] A new utility `agent.core.net_utils.check_ssl_error` is implemented.
- [ ] The utility detects `CERTIFICATE_VERIFY_FAILED` strings in exceptions from `urllib`, `requests`, `httpx`, etc.
- [ ] The utility returns a standardized, user-friendly error message instructing the user to check proxy/certificate settings.
- [ ] `notion_schema_manager.py` uses this utility.
- [ ] `download_models.py` uses this utility.
- [ ] `vad.py` (VAD model downloader) uses this utility.
- [ ] `agent.core.ai.service.py` (AI Provider calls) uses this utility for network errors.
- [ ] No module silently swallows SSL errors or bypasses verification automatically.

## Technical Notes

- Centralize the error string to avoid duplication.
- Ensure the utility is robust against different exception types (URLError, SSLError, ConnectError).
