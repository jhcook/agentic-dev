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

"""Context and prompt construction for the Implementation Agent."""

from agent.core.config import config

# Build S/R delimiter strings dynamically to avoid conflict with runbook parser
_SEARCH = '<' * 3 + 'SEARCH'
_SEP = '=' * 3
_REPLACE = '>' * 3


def build_implementation_system_prompt(license_instruction: str = '') -> str:
    """Construct the system instructions for the AI coding agent."""
    parts = [
        'You are an Implementation Agent.',
        'Your goal is to EXECUTE ALL tasks defined in the provided RUNBOOK.',
        '',
        'INSTRUCTIONS:',
        '- Use REPO-RELATIVE paths (e.g. .agent/src/agent/main.py).',
        '- For EXISTING files emit search/replace blocks:',
        '',
        'File: path/to/file.py',
        _SEARCH,
        'exact lines',
        _SEP,
        'replacement',
        _REPLACE,
        '',
        '- For NEW files emit complete file content as a fenced code block.',
        '',
        '* Every module, class, and function MUST have a PEP-257 docstring.' + license_instruction,
    ]
    return '\n'.join(parts)


def get_license_instruction() -> str:
    """Fetch license header requirement if configured."""
    template = config.get_app_license_header()
    if template:
        return (
            f'\n- **CRITICAL**: All new source code files MUST begin with '
            f'the following exact license header:\n{template}\n'
        )
    return ''
