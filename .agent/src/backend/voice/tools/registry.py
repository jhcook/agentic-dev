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

from .architect import list_adrs, read_adr, search_rules
from .project import list_stories, get_project_info, list_runbooks
from .git import get_git_status, get_git_diff, get_git_log, get_git_branch
from .qa import run_backend_tests, run_frontend_lint
from .security import scan_file_for_secrets
from .observability import get_recent_logs
from .create_tool import create_tool
from .list_capabilities import list_capabilities
from .read_tool_source import read_tool_source
from .get_installed_packages import get_installed_packages
from .docs import list_docs, read_doc, search_docs

def get_all_tools():
    """
    Return a list of all initialized tools for the agent.
    """
    base_tools = [
        # Architect
        list_adrs, read_adr, search_rules,
        # Project
        list_stories, get_project_info, list_runbooks,
        # Git
        get_git_status, get_git_diff, get_git_log, get_git_branch,
        # QA
        run_backend_tests, run_frontend_lint,
        # Security
        scan_file_for_secrets,
        # Observability
        get_recent_logs,
        # Meta
        create_tool, list_capabilities, read_tool_source, get_installed_packages,
        # Docs
        list_docs, read_doc, search_docs
    ]
    
    return base_tools
