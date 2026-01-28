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

from langchain_core.tools import tool
import subprocess
import logging
from backend.voice.events import EventBus
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

@tool
def get_git_status(config: RunnableConfig = None) -> str:
    """
    Get the current git status of the repository, categorized by Staged and Unstaged changes.
    Useful for checking what is ready to commit vs what is work in progress.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--short"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        if not result.stdout:
            return "Working tree clean."
            
        lines = result.stdout.strip().split('\n')
        
        staged = []
        unstaged = []
        untracked = []
        
        for line in lines:
            if len(line) < 3: continue
            index_status = line[0]
            work_status = line[1]
            path = line[3:]
            
            # Logic:
            # '??' -> Untracked
            # Index != ' ' and != '?' -> Staged
            # Work != ' ' and != '?' -> Unstaged
            
            if index_status == '?' and work_status == '?':
                untracked.append(path)
                continue
                
            if index_status != ' ':
                staged.append(f"{index_status} {path}")
                
            if work_status != ' ':
                unstaged.append(f"{work_status} {path}")

        output = []
        
        if staged:
            output.append(f"STAGED Changes ({len(staged)}):")
            output.extend([f"  {item}" for item in staged[:10]])
            if len(staged) > 10: output.append(f"  ...and {len(staged)-10} more")
            output.append("")
            
        if unstaged:
            output.append(f"UNSTAGED Changes ({len(unstaged)}):")
            output.extend([f"  {item}" for item in unstaged[:10]])
            if len(unstaged) > 10: output.append(f"  ...and {len(unstaged)-10} more")
            output.append("")
            
        if untracked:
            output.append(f"UNTRACKED Files ({len(untracked)}):")
            output.extend([f"  {item}" for item in untracked[:5]])
            if len(untracked) > 5: output.append(f"  ...and {len(untracked)-5} more")
            
        formatted_output = "\n".join(output)
        
        # Stream to console if session available
        if config:
            session_id = config.get("configurable", {}).get("thread_id", "unknown")
            EventBus.publish(session_id, "console", "\n=== Git Status ===\n" + formatted_output + "\n")
            
        return formatted_output
        
    except subprocess.CalledProcessError as e:
        return f"Error checking git status: {e}"

@tool
def get_git_diff(config: RunnableConfig = None) -> str:
    """
    Get the staged git diff. 
    Use this during preflight checks to see what is about to be committed.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        if not result.stdout:
            return "No staged changes."

        # Stream to console (Full output)
        if config:
            session_id = config.get("configurable", {}).get("thread_id", "unknown")
            EventBus.publish(session_id, "console", "\n=== Git Diff (Staged) ===\n" + result.stdout)

        # Truncate if too long (LLM context limit)
        if len(result.stdout) > 5000:
            return result.stdout[:5000] + "\n...[Truncated]"
        
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error checking git diff: {e}"

@tool
def get_git_log(limit: int = 5) -> str:
    """
    Get the recent git log history.
    Args:
        limit: Number of commits to show (default: 5)
    """
    try:
        result = subprocess.run(
            ["git", "log", f"-n {limit}", "--oneline"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error getting git log: {e}"
@tool
def get_git_branch() -> str:
    """
    Get the current active git branch name.
    Useful for inferring the current story or task context.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        branch_name = result.stdout.strip() or "HEAD (detached)"
        logger.info(f"Tool get_git_branch returned: {branch_name}")
        return f"Current Git Branch: {branch_name}"
    except subprocess.CalledProcessError as e:
        logger.error(f"Tool get_git_branch failed: {e}")
        return f"Error getting git branch: {e}"

@tool
def git_stage_changes(files: list[str] = None) -> str:
    """
    Stage files for commit.
    Args:
        files: List of file paths to stage. Defaults to ["."] (all changes).
    """
    targets = files if files else ["."]
    
    try:
        cmd = ["git", "add"] + targets
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Summarize for voice
        if "." in targets:
            return "Staged all changes."
        elif len(targets) > 3:
            return f"Staged {len(targets)} files."
        else:
            return f"Staged: {', '.join(targets)}"
            
    except subprocess.CalledProcessError as e:
        return f"Error staging changes: {e}"

@tool
def run_commit(message: str = None, config: RunnableConfig = None) -> str:
    """
    Commit staged changes to the repository.
    If no message is provided, AI generation will be used.
    """
    try:
        session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"

        # Use robust shell activation pattern
        base_cmd = "source .venv/bin/activate && agent commit --yes"
        
        if message:
            # Escape quotes in message
            safe_message = message.replace('"', '\\"')
            cmd = f'{base_cmd} -m "{safe_message}"'
        else:
            cmd = f"{base_cmd} --ai"
             
        # Execute with shell to support source
        process = subprocess.Popen(
            cmd,
            shell=True,
            executable='/bin/zsh',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        output_buffer = []
        
        # Stream output
        for line in iter(process.stdout.readline, ''):
            if line:
                EventBus.publish(session_id, "console", line)
                output_buffer.append(line)
        
        process.wait()
        
        if process.returncode == 0:
            # Fetch the commit details
            log_result = subprocess.run(
                ["git", "log", "-1", "--stat"],
                capture_output=True,
                text=True,
                check=False
            )
            return f"Commit successful.\n\n{log_result.stdout}"
        else:
            return f"Error committing changes:\n{''.join(output_buffer)}"
            
    except Exception as e:
        return f"Failed to run commit: {e}"

@tool
def run_pr(story_id: str = None, draft: bool = False, config: RunnableConfig = None) -> str:
    """
    Create a GitHub Pull Request for the current branch/story.
    Runs preflight checks automatically before creating the PR.
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
    
    # Generate ID
    process_id = f"pr-{story_id or 'new'}-{int(subprocess.check_output(['date', '+%s']).decode().strip())}"
    
    EventBus.publish(session_id, "console", f"> Starting PR Creation (ID: {process_id})...\n")
    
    try:
        # 1. Ensure branch is pushed
        # Use .func to bypass Tool wrapper overhead/validation for internal call
        push_result = git_push_branch.func(config=config)
        # Even if it returns error text, we might want to try PR anyway? 
        # But user said "ensure if HEAD is not pushed... do a push".
        # If push failed, PR creation might fail too.
        # Check output for success?
        if "Error" in push_result or "Failed" in push_result:
             EventBus.publish(session_id, "console", f"⚠️  Push Result: {push_result}\nContinuing with PR...\n")
        else:
             EventBus.publish(session_id, "console", f"✅ {push_result}\n")

        # 2. Build PR command
        cmd_parts = ["source .venv/bin/activate && agent pr"]
        if story_id:
            cmd_parts.append(f"--story {story_id}")
        if draft:
            cmd_parts.append("--draft")
        
        # Always use AI for summary generation
        cmd_parts.append("--ai")
            
        command = " ".join(cmd_parts)
        
        process = subprocess.Popen(
            command,
            shell=True,
            executable='/bin/zsh',
            cwd=None,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Register for interaction (e.g. preflight prompts)
        from backend.voice.process_manager import ProcessLifecycleManager
        ProcessLifecycleManager.instance().register(process, process_id)
        
        # Background reader
        def read_output():
            import threading
            import re
            
            pr_url = None
            
            try:
                for line in iter(process.stdout.readline, ''):
                    EventBus.publish(session_id, "console", f"[{process_id}] {line}")
                    
                    # Search for PR URL
                    # Example: https://github.com/org/repo/pull/123
                    if not pr_url:
                        match = re.search(r'(https://github\.com/[^/]+/[^/]+/pull/\d+)', line)
                        if match:
                            pr_url = match.group(1)
                
                process.stdout.close()
                rc = process.wait()
                
                if rc == 0:
                    EventBus.publish(session_id, "console", f"\n✅ PR Created Successfully (ID: {process_id}).\n")
                    if pr_url:
                        EventBus.publish(session_id, "console", f"Opening: {pr_url}\n")
                        EventBus.publish(session_id, "open_url", {"url": pr_url})
                else:
                    EventBus.publish(session_id, "console", f"\n❌ PR Creation Failed (ID: {process_id}).\n")
            except Exception as e:
                EventBus.publish(session_id, "console", f"[{process_id}] Error: {e}")
            finally:
                ProcessLifecycleManager.instance().unregister(process_id)

        import threading
        t = threading.Thread(target=read_output, daemon=True)
        t.start()
        
        return "PR creation started. Follow along below."
        
    except Exception as e:
        return f"Failed to start PR creation: {e}"

@tool
def git_push_branch(config: RunnableConfig = None) -> str:
    """
    Push the current branch to origin.
    Automatically handles setting the upstream branch if it's missing.
    """
    session_id = config.get("configurable", {}).get("thread_id", "unknown") if config else "unknown"
    EventBus.publish(session_id, "console", "> Pushing to origin...\n")

    try:
        # 1. Attempt standard push
        process = subprocess.Popen(
            ["git", "push"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        # Stream output
        if stdout: EventBus.publish(session_id, "console", stdout)
        if stderr: EventBus.publish(session_id, "console", stderr)

        # 2. Check for "no upstream" error
        # Typical message: "fatal: The current branch ... has no upstream branch."
        if process.returncode != 0 and "no upstream branch" in (stderr + stdout):
            EventBus.publish(session_id, "console", "⚠️  Upstream not set. Setting upstream to origin...\n")
            
            # Get current branch
            branch_proc = subprocess.run(
                ["git", "branch", "--show-current"], 
                capture_output=True, text=True, check=True
            )
            current_branch = branch_proc.stdout.strip()
            
            # Retry with --set-upstream
            cmd = ["git", "push", "--set-upstream", "origin", current_branch]
            retry_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            out, err = retry_proc.communicate()
            
            if out: EventBus.publish(session_id, "console", out)
            if err: EventBus.publish(session_id, "console", err)
            
            if retry_proc.returncode == 0:
                return f"Successfully pushed and set upstream for '{current_branch}'."
            else:
                return f"Failed to push even after setting upstream.\n{err}"

        elif process.returncode == 0:
            return "Successfully pushed to origin."
        else:
            return f"Error pushing branch:\n{stderr}"

    except Exception as e:
        return f"System error during push: {e}"
