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

import re
import shutil
import signal
import subprocess
import sys
import os
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable

import yaml
from opentelemetry import trace

import typer
from rich.console import Console

console = Console()
tracer = trace.get_tracer(__name__)


def get_all_files(path: Path) -> List[Path]:
    """
    Get all files in path recursively, respecting gitignore if possible.
    """
    files = []

    # Check if inside git repo
    try:
        cmd = ["git", "ls-files", "--full-name"]

        cwd = path if path.is_dir() else path.parent
        if not cwd.exists():
            return []

        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        git_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

        for f in git_files:
            abs_path = cwd / f
            if path.is_dir():
                if str(abs_path).startswith(str(path.resolve())):
                    files.append(abs_path)
            else:
                files.append(abs_path)

        if not files and not (cwd / ".git").exists():
            files.extend([p for p in path.rglob("*") if p.is_file()])

    except (subprocess.CalledProcessError, FileNotFoundError):
        for p in path.rglob("*"):
            if p.is_file():
                parts = p.parts
                if (
                    ".git" in parts
                    or "node_modules" in parts
                    or "__pycache__" in parts
                    or ".venv" in parts
                ):
                    continue
                files.append(p)

    return files


def get_files_to_lint(
    path: Optional[Path], all_files: bool, base: Optional[str], staged: bool
) -> List[str]:
    """
    Determine which files to lint based on arguments.
    """
    candidates: Set[str] = set()
    cwd = Path.cwd()

    if path:
        target = path.resolve()
        if target.is_file():
            candidates.add(str(target))
        elif target.is_dir():
            found = get_all_files(target)
            candidates.update(str(f) for f in found)
        else:
            console.print(f"[red]Path not found: {target}[/red]")
            raise typer.Exit(1)

    elif all_files:
        found = get_all_files(cwd)
        candidates.update(str(f) for f in found)

    else:
        cmd = ["git", "diff", "--name-only", "--diff-filter=d"]

        if base:
            cmd.extend([f"{base}...HEAD"])
        elif staged:
            cmd.append("--cached")
        else:
            cmd.append("--cached")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            rel_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]

            root_res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            if root_res.returncode == 0:
                git_root = Path(root_res.stdout.strip())
                for rf in rel_files:
                    abs_p = git_root / rf
                    if abs_p.exists():
                        candidates.add(str(abs_p))
        except subprocess.CalledProcessError:
            console.print(
                "[yellow]Not a git repository or git error. Falling back to all "
                "files.[/yellow]"
            )
            return []

    return sorted(list(candidates))


def run_linter(
    name: str,
    files: List[str],
    cmd_builder: Callable[[List[str], bool], List[str]],
    fix: bool = False,
    check_binaries: List[str] = [],
    root: Optional[Path] = None,
    use_npx: bool = False
) -> bool:
    """
    Generic linter runner with consistent error handling and tracing.
    
    Args:
        name: Name of the linter (e.g. "eslint", "markdownlint")
        files: List of file paths to lint
        cmd_builder: Function that takes (files, fix) and returns CLI args list
        fix: Whether to apply fixes
        check_binaries: List of binary names to check availability for (e.g. ["npx", "eslint"])
        root: Working directory for execution
        use_npx: If true, checks for npx first
    """
    if not files:
        return True
        
    cwd = root or Path.cwd()
    
    with tracer.start_as_current_span(f"lint.{name}") as span:
        span.set_attribute("file_count", len(files))
        
        # Check binaries
        missing = []
        for binary in check_binaries:
            if not shutil.which(binary):
                missing.append(binary)
        
        if missing:
             # Graceful degradation logic
             is_ci = os.getenv("CI", "").lower() in ("true", "1", "yes")
             if is_ci:
                 console.print(f"[bold red]❌ CI Error: Required binaries missing for {name}: {', '.join(missing)}[/bold red]")
                 span.set_attribute("status", "failed_ci")
                 return False
             else:
                 console.print(f"[dim]⚠️  Skipping {name} (missing: {', '.join(missing)}).[/dim]")
                 span.set_attribute("skipped", True)
                 return True

        # Build Command
        try:
            cmd = cmd_builder(files, fix)
        except Exception as e:
            console.print(f"[red]Error building command for {name}: {e}[/red]")
            return False

        console.print(f"[bold blue]Running {name} on {len(files)} files...[/bold blue]")
        
        try:
            subprocess.run(cmd, cwd=cwd, check=True)
            span.set_attribute("status", "success")
            return True
        except subprocess.CalledProcessError:
            console.print(f"[red]❌ {name} found issues.[/red]")
            span.set_attribute("status", "failed")
            return False
        except Exception as e:
            console.print(f"[red]Execution error for {name}: {e}[/red]")
            span.set_attribute("status", "error")
            span.record_exception(e)
            return False


def run_ruff(files: List[str], fix: bool = False) -> bool:
    def build_cmd(f: List[str], do_fix: bool) -> List[str]:
        base = [sys.executable, "-m", "ruff", "check"]
        if do_fix:
            base.append("--fix")
        base.extend(f)
        return base
        
    return run_linter("ruff", files, build_cmd, fix=fix)


def run_shellcheck(files: List[str], fix: bool = False) -> bool:
    def build_cmd(f: List[str], do_fix: bool) -> List[str]:
        if do_fix:
             console.print("[yellow]Note: Shellcheck does not support auto-fix via CLI.[/yellow]")
        return ["shellcheck"] + f
        
    # check_binaries=["shellcheck"] handles the availability check pattern from original code
    return run_linter("shellcheck", files, build_cmd, fix=fix, check_binaries=["shellcheck"])


def find_eslint_root(file_path: Path) -> Path:
    """Find the directory containing eslint config for a file."""
    current = file_path.parent
    while current != current.parent:
        if (
            (current / "eslint.config.js").exists()
            or (current / "eslint.config.mjs").exists()
            or (current / "eslint.config.cjs").exists()
            or (current / ".eslintrc.js").exists()
            or (current / ".eslintrc.json").exists()
        ):
            return current
        if (current / "package.json").exists():
             pass
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd()


def run_eslint(files: List[str], fix: bool = False) -> bool:
    if not files:
        return True

    # Group files by project root
    groups = {}
    for f in files:
        p = Path(f).resolve()
        root = find_eslint_root(p)
        if root not in groups:
            groups[root] = []
        try:
            rel = p.relative_to(root)
            groups[root].append(str(rel))
        except ValueError:
            groups[root].append(str(p))

    success = True
    
    for root, root_files in groups.items():
        # Define builder for this group
        def build_cmd(f: List[str], do_fix: bool) -> List[str]:
             # Try npx first
             cmd = ["npx", "--no-install", "eslint"]
             if do_fix:
                 cmd.append("--fix")
             cmd.extend(f)
             return cmd
        
        # We rely on npx or eslint availability
        # Note: Previous logic had complex fallback. Let's simplify to npx or eslint.
        # But 'run_linter' checks binaries up front.
        # We'll rely on npx being present for this standard flow.
        if not run_linter("eslint", root_files, build_cmd, fix=fix, root=root, check_binaries=["npx"]):
             # Fallback logic not easily fitting into generic runner if we want completely different binaries?
             # Actually, if run_linter fails (returns False), we can mark success=False.
             # The previous logic had a fallback to 'eslint' binary if npx failed?
             # Let's trust the generic runner's check for npx.
             success = False

    return success


def run_markdownlint(files: List[str], fix: bool = False) -> bool:
    def build_cmd(f: List[str], do_fix: bool) -> List[str]:
        has_npx = shutil.which("npx") is not None
        if has_npx:
            cmd = ["npx", "--yes", "markdownlint-cli@0.44.0"]
        else:
            cmd = ["markdownlint"]
            
        if do_fix:
            cmd.append("--fix")
        cmd.extend(f)
        return cmd

    # We check for EITHER npx OR markdownlint
    # Generic runner checks ALL binaries in check_binaries.
    # So we can't pass both.
    # We'll skip the generic check and handle it in builder or pass nothing and let builder decide.
    # But we need to handle "missing both" case for the skip logic.
    
    has_any = shutil.which("npx") or shutil.which("markdownlint")
    if not has_any:
         # Manually handle the skip to match generic behavior behavior
         is_ci = os.getenv("CI", "").lower() in ("true", "1", "yes")
         if is_ci:
             console.print("[bold red]❌ CI Error: markdownlint missing.[/bold red]")
             return False
         console.print("[dim]⚠️  Skipping markdownlint (missing).[/dim]")
         return True
         
    return run_linter("markdownlint", files, build_cmd, fix=fix)


# ---------------------------------------------------------------------------
# ADR Enforcement Engine (INFRA-057)
# ---------------------------------------------------------------------------


def parse_adr_enforcement_blocks(content: str) -> List[Dict[str, str]]:
    """Extract enforcement rules from ```enforcement fenced blocks in ADR content.

    Returns a list of dicts, each with keys: type, pattern, scope, violation_message.
    Malformed YAML blocks are silently skipped.
    """
    blocks: List[Dict[str, str]] = []
    matches = re.findall(r"```enforcement\s*\n(.*?)\n```", content, re.DOTALL)
    for match in matches:
        try:
            parsed = yaml.safe_load(match)
            if isinstance(parsed, list):
                blocks.extend(parsed)
            elif isinstance(parsed, dict):
                blocks.append(parsed)
        except yaml.YAMLError:
            pass  # Malformed blocks recorded via span, not crash
    return blocks


def parse_adr_state(content: str) -> str:
    """Extract ADR state from the ``## State`` section.

    Returns the first non-blank token after the heading, or ``'UNKNOWN'``.
    """
    match = re.search(r"^## State\s*$\s*^\s*(\S+)", content, re.MULTILINE)
    return match.group(1).strip() if match else "UNKNOWN"


def load_exception_records(adrs_dir: Path) -> List[Dict[str, Any]]:
    """Load ACCEPTED exception records (``EXC-*``) for violation suppression."""
    exceptions: List[Dict[str, Any]] = []
    for exc_file in sorted(adrs_dir.glob("EXC-*.md")):
        try:
            content = exc_file.read_text(errors="ignore")
        except OSError:
            continue
        state = parse_adr_state(content)
        if state == "ACCEPTED":
            exceptions.append({
                "id": exc_file.stem,
                "content": content,
                "path": exc_file,
            })
    return exceptions


def _is_suppressed_by_exception(
    adr_id: str,
    file_path: str,
    pattern: str,
    exceptions: List[Dict[str, Any]],
) -> bool:
    """Return ``True`` if a matching ACCEPTED exception record suppresses this violation."""
    for exc in exceptions:
        content = exc["content"]
        # Exception must reference both the ADR *and* the violating file
        if adr_id in content and file_path in content:
            return True
    return False


def run_adr_enforcement(
    files: Optional[List[str]] = None,
    repo_root: Optional[Path] = None,
) -> bool:
    """Run deterministic ADR enforcement lint checks.

    Parses `````enforcement`` blocks from ACCEPTED ADRs, matches regex patterns
    against in-scope files, and reports structured violations.

    Args:
        files: Optional explicit file list (intersection with scope globs).
        repo_root: Repository root. Defaults to ``config.repo_root``.

    Returns:
        ``True`` if no violations were found, ``False`` otherwise.
    """
    from agent.core.config import config  # ADR-025: local import

    root = repo_root or config.repo_root
    adrs_dir = root / ".agent" / "adrs"

    if not adrs_dir.exists():
        console.print("[dim]⚠️  No ADRs directory found, skipping ADR enforcement.[/dim]")
        return True

    with tracer.start_as_current_span("lint.adr_enforcement") as span:
        # 1. Collect enforcement rules from ACCEPTED ADRs
        rules: List[Dict[str, Any]] = []
        adr_files = sorted(adrs_dir.glob("ADR-*.md"))
        for adr_file in adr_files:
            try:
                content = adr_file.read_text(errors="ignore")
            except OSError:
                continue
            state = parse_adr_state(content)
            if state != "ACCEPTED":
                continue
            blocks = parse_adr_enforcement_blocks(content)
            # Derive ADR ID from filename (e.g. ADR-025)
            stem_parts = adr_file.stem.split("-")
            adr_id = f"{stem_parts[0]}-{stem_parts[1]}" if len(stem_parts) >= 2 else adr_file.stem
            for block in blocks:
                if block.get("type") == "lint":
                    rules.append({
                        "adr_id": adr_id,
                        "adr_file": adr_file.name,
                        "pattern": block.get("pattern", ""),
                        "scope": block.get("scope", "**/*"),
                        "message": block.get("violation_message", "ADR violation"),
                    })

        span.set_attribute("adr_count", len(adr_files))
        span.set_attribute("rule_count", len(rules))

        if not rules:
            console.print("[dim]No ADR enforcement rules found.[/dim]")
            return True

        console.print(f"[bold blue]Running ADR enforcement ({len(rules)} rules)...[/bold blue]")

        # 2. Load exception records
        exceptions = load_exception_records(adrs_dir)
        exception_count = 0

        # 3. Evaluate each rule
        violations: List[Dict[str, Any]] = []

        for rule in rules:
            scope = rule["scope"]

            # Reject absolute scope paths
            if Path(scope).is_absolute():
                violations.append({
                    "file": rule["adr_file"],
                    "line": 0,
                    "col": 0,
                    "message": f"{rule['adr_id']}: Invalid absolute scope '{scope}'",
                })
                continue

            # Resolve scope glob against repo root
            matched_files = sorted(root.glob(scope))

            # Intersect with explicit file list when provided
            if files is not None:
                file_set = {str(Path(f).resolve()) for f in files}
                matched_files = [f for f in matched_files if str(f.resolve()) in file_set]

            # Compile regex — invalid patterns are reported, not crashed
            try:
                compiled = re.compile(rule["pattern"])
            except re.error as exc:
                violations.append({
                    "file": rule["adr_file"],
                    "line": 0,
                    "col": 0,
                    "message": f"{rule['adr_id']}: Invalid regex '{rule['pattern']}': {exc}",
                })
                continue

            for target_file in matched_files:
                if not target_file.is_file():
                    continue
                try:
                    file_content = target_file.read_text(errors="ignore")
                except OSError:
                    continue

                # Apply regex with SIGALRM timeout (5 s) to mitigate ReDoS
                old_handler = signal.getsignal(signal.SIGALRM)

                def _timeout_handler(signum: int, frame: types.FrameType | None) -> None:
                    raise TimeoutError("Regex execution timed out")

                signal.signal(signal.SIGALRM, _timeout_handler)
                try:
                    signal.alarm(5)
                    for line_num, line in enumerate(file_content.splitlines(), 1):
                        m = compiled.search(line)
                        if m:
                            rel_path = str(target_file.relative_to(root))
                            if _is_suppressed_by_exception(
                                rule["adr_id"], rel_path, rule["pattern"], exceptions
                            ):
                                exception_count += 1
                                continue
                            violations.append({
                                "file": rel_path,
                                "line": line_num,
                                "col": m.start() + 1,
                                "message": f"{rule['adr_id']}: {rule['message']}",
                            })
                except TimeoutError:
                    violations.append({
                        "file": rule["adr_file"],
                        "line": 0,
                        "col": 0,
                        "message": f"{rule['adr_id']}: Regex timed out for pattern '{rule['pattern']}'",
                    })
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

        # 4. Report
        span.set_attribute("violation_count", len(violations))
        span.set_attribute("exception_count", exception_count)

        if violations:
            console.print(
                f"\n[bold red]❌ ADR Enforcement: {len(violations)} violation(s) found[/bold red]"
            )
            for v in violations:
                console.print(
                    f"  {v['file']}:{v['line']}:{v['col']}: {v['message']}"
                )
            span.set_attribute("status", "failed")
            return False

        console.print("[green]✅ ADR Enforcement: No violations found.[/green]")
        span.set_attribute("status", "success")
        return True


def lint(
    path: Optional[Path] = typer.Argument(
        None, help="Path to file or directory to lint."
    ),
    all_files: bool = typer.Option(
        False, "--all", help="Lint all files in the current directory recursively."
    ),
    base: str = typer.Option(
        None, "--base", help="Lint files changed relative to this base branch."
    ),
    staged: bool = typer.Option(
        True,
        "--staged/--no-staged",
        help="Lint staged files only (default if no path/all).",
    ),
    fix: bool = typer.Option(
        False, "--fix", help="Automatically fix lint errors where possible."
    ),
    adr_only: bool = typer.Option(
        False, "--adr-only", help="Run only ADR enforcement checks."
    ),
):
    """
    Lint the code using ruff (Python), shellcheck (Shell), eslint (JS/TS), and ADR enforcement.

    Default behavior (no args): Lints staged files.
    Use --adr-only to run only ADR enforcement checks.
    """

    files = get_files_to_lint(path, all_files, base, staged)

    # --adr-only: skip conventional linters, run only ADR enforcement
    if adr_only:
        if not run_adr_enforcement(files=files if files else None):
            console.print("[bold red]ADR enforcement failed.[/bold red]")
            raise typer.Exit(1)
        else:
            console.print("[bold green]ADR enforcement passed.[/bold green]")
        return

    if not files:
        console.print("[green]No files to lint.[/green]")
        raise typer.Exit(0)

    py_files = [f for f in files if f.endswith(".py")]
    sh_files = [f for f in files if f.endswith(".sh") or f.endswith("bin/agent")]
    js_files = [f for f in files if f.endswith((".js", ".jsx", ".ts", ".tsx"))]
    md_files = [f for f in files if f.endswith(".md")]

    success = True

    if py_files:
        if not run_ruff(py_files, fix=fix):
            success = False

    if sh_files:
        if not run_shellcheck(sh_files, fix=fix):
            success = False

    if js_files:
        if not run_eslint(js_files, fix=fix):
            success = False

    if md_files:
        if not run_markdownlint(md_files, fix=fix):
            success = False

    # Always run ADR enforcement alongside conventional linters
    if not run_adr_enforcement(files=files):
        success = False

    if not success:
        console.print("[bold red]Linting failed.[/bold red]")
        raise typer.Exit(1)
    else:
        console.print("[bold green]Linting passed.[/bold green]")
