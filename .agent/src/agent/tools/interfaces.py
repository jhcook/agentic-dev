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
Interfaces and Type Definitions for INFRA-144 Tool Domains.

This module defines the structured output contracts for web, testing,
dependency, and context tools to ensure consistent LLM processing.
"""

from typing import TypedDict, List, Optional, Union


from typing import Any, Union, List, Dict

class TestSuiteExecution(TypedDict):
    """
    Detailed output for test execution.
    
    Attributes:
        passed (int): Total number of passed tests.
        failed (int): Total number of failed tests.
        errors (int): Total number of setup/teardown errors.
        coverage_pct (float): Overall test coverage percentage.
        raw_output (str): Full console output from the test runner.
    """
    passed: int
    failed: int
    errors: int
    coverage_pct: float
    raw_output: str

class AuditVulnerability(TypedDict, total=False):
    """
    Details of a specific dependency vulnerability.
    
    Attributes:
        id (str): The CVE or vulnerability identifier.
        fix_versions (List[str]): Available versions that patch the vulnerability.
        aliases (List[str]): Alternative identifiers for the vulnerability.
        description (str): Detailed explanation of the vulnerability.
    """
    id: str
    fix_versions: List[str]
    aliases: List[str]
    description: str

class AuditDependencyResult(TypedDict, total=False):
    """
    Result of pip-audit for a single dependency.
    
    Attributes:
        name (str): The name of the vulnerable package.
        version (str): The installed version of the package.
        vulns (List[AuditVulnerability]): List of identified vulnerabilities for this package.
    """
    name: str
    version: str
    vulns: List[AuditVulnerability]

class WebToolResult(TypedDict, total=False):
    """
    Structured result wrapper for Web tools.
    
    Attributes:
        success (bool): Indicates if the web operation was successful.
        output (str): The resulting data (e.g., Markdown content) on success.
        error (str): Error message if the operation failed.
    """
    success: bool
    output: str
    error: str

class TestingToolResult(TypedDict, total=False):
    """
    Structured result wrapper for Testing tools.
    
    Attributes:
        success (bool): Indicates if the testing operation was successful.
        output (Union[TestSuiteExecution, str]): Structured execution details or string placeholder.
        error (str): Error message if the operation failed.
    """
    success: bool
    output: Union[TestSuiteExecution, str]
    error: str

class DepsToolResult(TypedDict, total=False):
    """
    Structured result wrapper for Dependency tools.
    
    Attributes:
        success (bool): Indicates if the dependency operation was successful.
        output (Union[str, List[AuditDependencyResult]]): String message or list of vulnerabilities.
        error (str): Error message if the operation failed.
    """
    success: bool
    output: Union[str, List[AuditDependencyResult]]
    error: str

class ContextToolResult(TypedDict, total=False):
    """
    Structured result wrapper for Context tools.
    
    Attributes:
        success (bool): Indicates if the context operation was successful.
        output (str): The resulting data (e.g., diff or reference) on success.
        error (str): Error message if the operation failed.
    """
    success: bool
    output: str
    error: str
