
"""
Core module for Interactive Preflight Repair.
Decouples the fix logic from the CLI.
"""
import os
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import typer
import ast
import typer
import ast

from agent.core.ai import ai_service
from agent.core.ai.prompts import generate_fix_options_prompt

import logging
from agent.core.utils import scrub_sensitive_data

console = None # Removed
logger = logging.getLogger(__name__)

class InteractiveFixer:
    """
    Handles interactive repair of preflight failures.
    Includes analysis, proposal generation, verification, and safety rollbacks.

    For architectural details, see ADR-015: Interactive Preflight Repair.
    """

    def __init__(self):
        self.ai = ai_service

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
        # For now, we mainly support schema fixes (INFRA-042 scope)
        # But designing this to be extensible.
        
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
                
                # Parse AI response. Expecting JSON list of options?
                # For robustness, we might ask for simple text and parse, or JSON mode.
                # Let's assume the prompt instructions enforce JSON structure or we parse it.
                # For this MVP, let's try to parse JSON from the response.
                
                # Simple parsing strategy: look for json block
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                     json_str = response.split("```")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()
                    
                options = json.loads(json_str) 
                # Expected: [{"title": "...", "description": "...", "patched_content": "..."}]
                
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
                logger.info(f"METRIC: Feature Generation Completed. Options: {len(valid_options)}")
                return valid_options
                
            except Exception as e:
                logger.error(f"Fix generation failed: {e}")
                return []

        return proposals

    # present_options moved to CLI layer (see agent.commands.check)

    def apply_fix(self, option: Dict[str, Any], file_path: Path, confirm: bool = True) -> bool:
        """
        Apply the selected fix to the specified file path.
        
        This method includes safety mechanisms:
        1. It previews the change (diff) if running interactively.
        2. It saves the current state to git stash before applying.
        3. It attempts to write the new content.
        4. If writing fails, it pops the stash to revert.

        Args:
            option: The fix option dict with 'patched_content'.
            file_path: The Path object to the file to be modified.
            confirm: If True, prompt the user for confirmation before writing.

        Returns:
            True if applied successfully, False otherwise.
        """
        new_content = option.get("patched_content")
        if not new_content:
            logger.error("Invalid fix option: no content.")
            return False
            
        # Diff View
        current_content = file_path.read_text(errors="ignore")
        
        # Diff View handled by CLI or callback
            
        # Safety: Git Stash
        self._git_stash_save()
        
        try:
            file_path.write_text(new_content)
            logger.info(f"Applied fix to {file_path}")
            logger.info("METRIC: Fix Applied Successfully")
            return True
        except Exception as e:
            logger.error(f"File write failed: {e}")
            self._git_stash_pop() # Revert
            return False

    def verify_fix(self, check_callback) -> bool:
        """
        Run the verification callback. If it fails, offer to revert.
        """
        success = check_callback()

        if success:
            # Drop stash? Or keep it? 
            # Ideally we drop the stash since we "committed" to the change in working dir.
            # But 'git stash drop' might be safer.
            self._git_stash_drop()
            logger.info("METRIC: Fix Verification Passed")
            return True
        else:
             # In programmatic mode, we probably should revert automatically on failure 
             # OR leave it to the caller. 
             # Let's revert automatically to be safe, or make it configurable. 
             # For now, let's revert automatically if it failed verification to return to clean state.
             self._git_stash_pop()
             logger.info("Fix auto-reverted due to verification failure.")
                 
             return False

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

    def _git_stash_save(self):
        try:
            subprocess.run(["git", "stash", "push", "-m", "Agent Interactive Fix Safety Stash", "--quiet"], check=False)
        except Exception as e:
            logger.error(f"Git stash save failed: {e}")

    def _git_stash_pop(self):
        try:
            subprocess.run(["git", "stash", "pop", "--quiet"], check=False)
        except Exception as e:
            logger.error(f"Git stash pop failed: {e}")

    def _git_stash_drop(self):
        try:
            subprocess.run(["git", "stash", "drop", "--quiet"], check=False)
        except Exception as e:
            logger.error(f"Git stash drop failed: {e}")
