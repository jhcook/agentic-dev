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
Core module for Interactive Preflight Repair.
Decouples the fix logic from the CLI.
"""
import os
import shutil
import tempfile
import ast
import json
import logging
from typing import List, Dict, Any
from pathlib import Path

# typer/subprocess imports removed if unused, but kept if needed by other parts not shown

from agent.core.ai import ai_service
from agent.core.ai.prompts import generate_fix_options_prompt
from agent.core.utils import extract_json_from_response

console = None 
logger = logging.getLogger(__name__)

class InteractiveFixer:
    """
    Handles interactive repair of preflight failures.
    Includes analysis, proposal generation, verification, and safety rollbacks.

    For architectural details, see ADR-015: Interactive Preflight Repair.
    """

    def __init__(self):
        self.ai = ai_service
        # Track active backups: { str(original_path): str(backup_temp_path) }
        self._active_backups: Dict[str, str] = {}

    def analyze_failure(self, failure_type: str, context: Dict[str, Any], feedback: str = None) -> List[Dict[str, Any]]:
        """
        Analyze a failure and generate fix proposals.
        
        Args:
            failure_type: "story_schema", "linter", "check", etc.
            context: Metadata about the failure (e.g., missing keys, file path).
            feedback: Optional user feedback to refine the proposals.
            
        Returns:
            List of fix options (dicts).
        """
        proposals = []
        
        if failure_type == "story_schema":
            story_id = context.get("story_id")
            missing_sections = context.get("missing_sections", [])
            file_path = context.get("file_path")
            
            if not file_path:
                return []
            
            logger.info(f"METRIC: Analysis Started for {failure_type} on {story_id}")
                
            # Path Security/Traversal Check
            try:
                path = Path(file_path).resolve()
                repo_root = Path.cwd().resolve()
                
                # Use os.path.commonpath for robust prefix checking
                try:
                    if os.path.commonpath([str(path), str(repo_root)]) != str(repo_root):
                         logger.warning(f"Security Alert: Path traversal attempt: {path} (Repo Root: {repo_root})")
                         logger.info(f"METRIC: Security Violation Detected (Path): {path}")
                         return []
                except ValueError:
                     # Paths on different drives or other issues
                     logger.warning(f"Security Alert: Path checking failed for {path}")
                     return []

                if not path.exists():
                    logger.warning(f"File not found: {path} in analyze_failure")
                    return []
            except Exception as e:
                logger.error(f"Path resolution failed: {e}")
                return []
                
            content = path.read_text(errors="ignore")

            # Ask AI for options
            prompt = generate_fix_options_prompt(
                failure_type="story_schema",
                context={
                    "story_id": story_id,
                    "missing_sections": missing_sections,
                    "content": content
                },
                feedback=feedback
            )
            
            try:
                # Callback hook for UI progress if needed
                if feedback: 
                     logger.info("Generating fix options...")
                response = self.ai.get_completion(prompt)
                
                if not response or not response.strip():
                     logger.warning("AI returned empty response for fix generation.")
                     raise ValueError("AI returned empty response (possibly blocked or rate limited).")

                # Use shared extraction logic
                json_str = extract_json_from_response(response)

                try:
                    options = json.loads(json_str)
                except (json.JSONDecodeError, AttributeError):
                    # Log the first 200 chars to help debug "nonsense" checks
                    preview = response[:200].replace("\n", " ")
                    logger.warning(f"AI returned invalid JSON: '{preview}...'")
                    raise ValueError("AI response was not valid JSON.") 
                
                valid_options = []
                for opt in options:
                    # Schema Validation
                    if not isinstance(opt, dict) or "title" not in opt or "patched_content" not in opt:
                        logger.warning("Rejected malformed AI option (missing keys).")
                        continue
                        
                    if self._validate_fix_content(opt.get("patched_content", "")):
                        valid_options.append(opt)
                    else:
                        logger.warning(f"Rejected unsafe fix option: {opt.get('title')}")
                        logger.info("METRIC: Fix Validation Failed (Security)")
                
                logger.info(f"Generated {len(valid_options)} valid fix options for {failure_type}")
                
                # Limit options to prevent UI overload
                MAX_FIX_OPTIONS = 3
                if len(valid_options) > MAX_FIX_OPTIONS:
                    logger.info(f"Truncating fix options from {len(valid_options)} to {MAX_FIX_OPTIONS}")
                    valid_options = valid_options[:MAX_FIX_OPTIONS]

                logger.info(f"METRIC: Feature Generation Completed. Options: {len(valid_options)}")
                return valid_options
                
            except Exception as e:
                logger.warning(f"AI fix generation failed (falling back to manual): {e}")
                # Fallback to manual
                return [{
                    "title": "Manual Fix (Open in Editor)",
                    "description": "AI generation failed. Open the file to fix manually.",
                    "patched_content": content,
                    "action": "open_editor"
                }]

        elif failure_type == "governance_rejection":
            # Context: { "story_id": ..., "findings": [str], "file_path": ... }
            story_id = context.get("story_id")
            findings = context.get("findings", [])
            file_path = context.get("file_path")
            
            if not file_path:
                logger.warning("No file path provided for governance repair.")
                return []
                
            try:
                path = Path(file_path).resolve()
                if not path.exists():
                     return []
                content = path.read_text(errors="ignore")
            except Exception:
                return []

            prompt = generate_fix_options_prompt(
                failure_type="governance_rejection",
                context={
                    "story_id": story_id,
                    "findings": findings,
                    "content": content
                },
                feedback=feedback
            )
            
            try:
                logger.info("Generating governance fix options...")
                response = self.ai.get_completion(prompt)
                
                # Legacy split logic removed

                    
                if not response or not response.strip():
                     logger.warning("AI returned empty response for governance fix.")
                     raise ValueError("AI returned empty response (possibly blocked or rate limited).")
                
                # Use shared extraction logic from utils (DRY Fix)
                json_str = extract_json_from_response(response)

                try:
                    # Relaxed parsing to allow control characters (newlines) in strings
                    options = json.loads(json_str, strict=False)
                except (json.JSONDecodeError, AttributeError):
                     preview = response[:200].replace("\n", " ")
                     logger.warning(f"AI returned invalid JSON: '{preview}...'")
                     raise ValueError("AI response was not valid JSON.")
                
                valid_options = []
                for opt in options:
                    if not isinstance(opt, dict) or "title" not in opt or "patched_content" not in opt:
                        continue
                        
                    # Validate content safety
                    if self._validate_fix_content(opt.get("patched_content", "")):
                        valid_options.append(opt)
                
                # Limit options to prevent UI overload
                MAX_FIX_OPTIONS = 3
                if len(valid_options) > MAX_FIX_OPTIONS:
                    logger.info(f"Truncating fix options from {len(valid_options)} to {MAX_FIX_OPTIONS}")
                    valid_options = valid_options[:MAX_FIX_OPTIONS]

                return valid_options
                
            except Exception as e:
                logger.warning(f"Governance fix generation failed (falling back to manual): {e}")
                return [{
                    "title": "Manual Fix (Open in Editor)",
                    "description": "AI generation failed. Open the file to fix manually.",
                    "patched_content": content,
                    "action": "open_editor"
                }]

        return proposals

        return proposals

    def apply_fix(self, option: Dict[str, Any], file_path: Path, confirm: bool = True) -> bool:
        """
        Apply the selected fix to the specified file path.
        """
        # Handle special manual action
        if option.get("action") == "open_editor":
            import subprocess
            import platform
            
            editor = os.getenv("EDITOR", "vim")
            # Try to be smart about editor
            if not os.getenv("EDITOR"):
                 if platform.system() == "Windows": editor = "notepad"
                 elif shutil.which("nano"): editor = "nano"
                 elif shutil.which("vi"): editor = "vi"
            
            try:
                subprocess.run([editor, str(file_path)], check=True)
                logger.info(f"Opened {file_path} in {editor}")
                return True
            except Exception as e:
                logger.error(f"Failed to open editor: {e}")
                return False

        new_content = option.get("patched_content")
        if not new_content:
            logger.error("Invalid fix option: no content.")
            return False
            
        file_str = str(file_path.resolve())

        # Safety: File Backup (Replaces dangerous git stash)
        try:
            # Create a temp file for backup
            fd, backup_path = tempfile.mkstemp(prefix="agent_fix_backup_")
            os.close(fd) # Close file descriptor, we just need path
            
            shutil.copy2(file_path, backup_path)
            self._active_backups[file_str] = backup_path
            logger.debug(f"Backed up {file_path} to {backup_path}")
        except Exception as e:
             logger.error(f"Failed to create backup: {e}")
             return False
        
        try:
            file_path.write_text(new_content)
            logger.info(f"Applied fix to {file_path}")
            logger.info("METRIC: Fix Applied Successfully")
            return True
        except Exception as e:
            logger.error(f"File write failed: {e}")
            # Immediate Revert on Write Fail
            self._restore_backup(file_str, file_path)
            return False

    def verify_fix(self, check_callback) -> bool:
        """
        Run the verification callback. If it fails, restore from backup.
        """
        success = check_callback()

        # We assume verify_fix is called immediately after apply_fix on the same file context.
        # Ideally verify_fix should accept file_path, but check_callback encapsulates it.
        # We process ALL active backups. In a single-fix flow, there is only one.
        
        paths_to_clear = []

        if success:
            logger.info("METRIC: Fix Verification Passed")
            # Success: Delete backups
            for original_path, backup_path in self._active_backups.items():
                try:
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                except Exception as e:
                    logger.warning(f"Failed to cleanup backup {backup_path}: {e}")
                paths_to_clear.append(original_path)
        else:
             logger.info("Fix auto-reverted due to verification failure.")
             # Failure: Restore all backups
             for original_path, backup_path in self._active_backups.items():
                 try:
                     shutil.copy2(backup_path, original_path)
                     logger.info(f"Restored {original_path} from backup.")
                     os.remove(backup_path)
                 except Exception as e:
                     logger.error(f"Failed to restore backup for {original_path}: {e}")
                 paths_to_clear.append(original_path)

        # Clear backup registry
        for p in paths_to_clear:
            self._active_backups.pop(p, None)

        return success

    def _restore_backup(self, original_path_str: str, target_path: Path):
        """Helper to restore a specific backup."""
        backup = self._active_backups.get(original_path_str)
        if backup and os.path.exists(backup):
            try:
                shutil.copy2(backup, target_path)
                os.remove(backup)
                del self._active_backups[original_path_str]
                logger.info(f"Restored {target_path} from safety backup.")
            except Exception as e:
                logger.error(f"CRITICAL: Failed to restore backup for {target_path}: {e}")

    def _validate_fix_content(self, content: str) -> bool:
        """
        Validate that the proposed content is safe.
        Uses AST parsing for Python code and string checks for others.
        """
        # 1. String-based fast fail (Expanded Blacklist)
        suspicious_strings = [
            "import os", "import subprocess", "import sys", "import shutil", "import socket",
            "exec(", "eval(", "__import__", "shutil.rmtree", "subprocess", "os.system", "open(",
            "importlib", "__builtins__", "pickle", "marshal", "base64.b64decode"
        ]
        for pattern in suspicious_strings:
            if pattern in content:
                logger.warning(f"Security Alert: Fix content contains suspicious pattern '{pattern}'")
                logger.info(f"METRIC: Security Violation Detected (String): {pattern}")
                return False

        # 2. AST-based check (if Python)
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        if alias.name.split('.')[0] in ["os", "subprocess", "sys", "shutil", "socket", "importlib", "pickle", "marshal"]:
                             logger.warning(f"Security Alert: AST detected forbidden import '{alias.name}'")
                             return False
                elif isinstance(node, ast.Call):
                     if isinstance(node.func, ast.Name) and node.func.id in ["eval", "exec", "__import__", "open", "globals", "locals"]:
                         logger.warning(f"Security Alert: AST detected dangerous call '{node.func.id}'")
                         return False
                     # Detect Attribute calls like os.system
                     if isinstance(node.func, ast.Attribute) and node.func.attr in ["system", "popen", "spawn", "call", "check_call"]:
                         logger.warning(f"Security Alert: AST detected dangerous attribute call '{node.func.attr}'")
                         return False
        except SyntaxError:
            # Not valid Python, rely on string checks
            pass
        except Exception as e:
            logger.error(f"AST validation error: {e}")
            # Fail closed if validation completely breaks
            return False

        return True
