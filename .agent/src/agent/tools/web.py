# Copyright 2026 Justin Cook
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Web domain tools for fetching and processing online documentation.
"""

import requests
from pathlib import Path
from agent.core.utils import logger
from typing import Any, Dict, Optional
from markdownify import markdownify as md
from bs4 import BeautifulSoup
from agent.core.governance.audit_handler import audit_tool
from agent.tools.interfaces import WebToolResult
from agent.core.net_utils import fetch_with_resource_guards

@audit_tool(domain="web", action="fetch_url")
def fetch_url(url: str, repo_root: Optional[Path] = None) -> WebToolResult:
    """
    Fetches the content of a URL and converts it to markdown.

    Args:
        url: The HTTP URL to fetch.
        repo_root: Unused, provided for interface consistency.

    Returns:
        A dictionary containing the markdown content or an error message.
    """
    try:
        raw_bytes = fetch_with_resource_guards(url, max_bytes=1048576)
        html_content = raw_bytes.decode('utf-8')
        markdown = md(html_content, heading_style="ATX")

        return {
            "success": True,
            "output": markdown.strip()
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"Request to {url} timed out."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch URL: {str(e)}"
        }

@audit_tool(domain="web", action="read_docs")
def read_docs(url: str, repo_root: Optional[Path] = None) -> WebToolResult:
    """
    Fetches a URL and cleans it specifically for LLM consumption.

    Args:
        url: The documentation URL.
        repo_root: Unused.

    Returns:
        Cleaned markdown content.
    """
    res = fetch_url(url)
    if not res["success"]:
        return res

    # Further cleaning could be implemented here to remove nav/footers
    return res
