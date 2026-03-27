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

"""Syntax validator to cross-reference AI claims against py_compile results."""

import py_compile
import tempfile
import os
import re
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

def cross_validate_syntax_findings(findings: List[str]) -> List[str]:
    """Verify AI syntax error claims against deterministic compilation.

    If a finding claims a 'syntax error' at a specific line, this runs py_compile.
    If the file compiles without error, the finding is auto-dismissed as a hallucination.
    """
    validated_findings = []
    
    for finding in findings:
        finding_lower = finding.lower()
        if "syntax error" not in finding_lower and "invalid syntax" not in finding_lower:
            validated_findings.append(finding)
            continue

        # Extract file path from finding
        file_match = re.search(r'[`"]?([a-zA-Z0-9_/.-]+\.py)[`"]?', finding)
        if not file_match:
            validated_findings.append(finding)
            continue
            
        filepath_str = file_match.group(1)
        # Try to resolve path relative to repo
        fpath = Path.cwd() / filepath_str
        if not fpath.exists():
            # Try stripping common prefixes
            for prefix in [".agent/src/", "agent/", "backend/"]:
                candidate = Path.cwd() / prefix / filepath_str
                if candidate.exists():
                    fpath = candidate
                    break
        
        if not fpath.exists() or fpath.is_dir():
            validated_findings.append(finding)
            continue

        try:
            # Attempt to compile the file to a temporary location
            with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                py_compile.compile(str(fpath), cfile=tmp_path, doraise=True)
                # If we reach here, compilation succeeded.
                # The AI claim of a syntax error is a false positive.
                logger.info("Syntax finding dismissed (file compiles cleanly): %s", finding[:80])
            except py_compile.PyCompileError:
                # The AI was right; there is a syntax error.
                validated_findings.append(finding)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            logger.debug("Syntax validation failed for %s: %s", fpath, e)
            validated_findings.append(finding)
            
    return validated_findings
