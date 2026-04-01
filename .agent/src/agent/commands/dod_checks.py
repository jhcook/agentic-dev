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

"""DoD (Definition of Done) Compliance Gate helpers.

Extracted from ``utils.py`` (INFRA-165) to keep module LOC under the
1000-line quality gate.  All public names are re-exported from ``utils``
for backward compatibility.
"""

import re as _re
from pathlib import Path, PurePosixPath
from typing import List


def extract_acs(story_content: str) -> List[str]:
    """Extract Acceptance Criteria bullets from a story markdown file.

    Scans for the ``## Acceptance Criteria`` section and returns each
    non-empty bullet line (stripping leading ``- [ ]`` / ``- [x]`` markers).

    Args:
        story_content: Raw markdown text of the user story.

    Returns:
        List of AC strings.  Empty list if the section is absent.
    """
    ac_section = _re.search(
        r"##\s+Acceptance Criteria\s*\n(.*?)(?=\n##|\Z)",
        story_content,
        _re.DOTALL | _re.IGNORECASE,
    )
    if not ac_section:
        return []
    raw = ac_section.group(1)
    acs: List[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = _re.sub(r"^-\s*\[.\]\s*", "", stripped)
        cleaned = _re.sub(r"^[-*]\s+", "", cleaned)
        if cleaned:
            acs.append(cleaned)
    return acs


def build_ac_coverage_prompt(acs: List[str], runbook_content: str) -> str:
    """Build the secondary AI prompt for AC-1 coverage check.

    Asks the AI to identify which Acceptance Criteria from the story are NOT
    addressed by any step in the runbook.  The response format is strictly
    ``ALL_PASS`` (all covered) or one ``AC-N: <reason>`` line per gap.

    Args:
        acs: List of AC strings extracted from the parent story.
        runbook_content: Raw runbook markdown (implementation steps only).

    Returns:
        Prompt string to send to the AI for AC coverage analysis.
    """
    numbered = "\n".join(f"AC-{i + 1}: {ac}" for i, ac in enumerate(acs))
    # Trim runbook to the Implementation Steps section to keep prompt compact
    impl_match = _re.search(
        r"#+\s*Implementation Steps?\s*\n(.*?)(?=\n#+|\Z)",
        runbook_content,
        _re.DOTALL | _re.IGNORECASE,
    )
    steps_text = impl_match.group(1).strip() if impl_match else runbook_content[:4000]

    return (
        "You are a strict QA reviewer. Given the Acceptance Criteria (ACs) for a "
        "user story and the Implementation Steps in a runbook, identify which ACs "
        "are NOT addressed by any step in the runbook.\n\n"
        f"## Acceptance Criteria\n{numbered}\n\n"
        f"## Runbook Implementation Steps\n{steps_text}\n\n"
        "## Instructions\n"
        "Return ONLY one of:\n"
        "  • The literal string `ALL_PASS` if every AC is addressed.\n"
        "  • One line per unaddressed AC in the format `AC-N: <brief reason>`.\n"
        "Do NOT include any prose, preamble, or explanation outside this format."
    )


def parse_ac_gaps(ai_response: str) -> List[str]:
    """Parse the AI response from an AC coverage check.

    Args:
        ai_response: Raw string returned by the AI for AC coverage analysis.

    Returns:
        List of gap IDs (e.g. ``['AC-1', 'AC-3']``).  Empty list if all pass.
    """
    text = ai_response.strip()
    if not text or "ALL_PASS" in text:
        return []
    gaps: List[str] = []
    for match in _re.finditer(r"^(AC-\d+):", text, _re.MULTILINE):
        gaps.append(match.group(1))
    return gaps


def check_test_coverage(runbook_content: str) -> List[str]:
    """Check that every ``[NEW]`` implementation file has a paired test file step.

    For each ``[NEW]`` non-test ``.py`` file found in the runbook, verifies that a
    corresponding ``[NEW]`` or ``[MODIFY]`` step targeting a ``test_<module>.py``
    (or ``<module>_test.py``) file also exists.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings — one per unpaired implementation file (empty if all pass).
    """
    pattern = _re.compile(
        r"####\s+\[(NEW|MODIFY)\]\s+([^\n]+)",
        _re.IGNORECASE,
    )

    # Source code extensions that DO need paired tests.
    # Everything else (config, docs, data, rules, templates, etc.) is excluded.
    _SOURCE_EXTS = {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".go", ".rs", ".java", ".kt", ".swift", ".rb", ".php",
        ".c", ".cpp", ".h", ".hpp", ".cs",
    }
    # Boilerplate files that don't need paired tests
    _BOILERPLATE_STEMS = {"__init__", "conftest", "__main__", "setup"}

    impl_files: List[str] = []
    test_stems: set[str] = set()

    for m in pattern.finditer(runbook_content):
        action = m.group(1).upper()  # "NEW" or "MODIFY"
        path = m.group(2).strip()
        pp = PurePosixPath(path)
        stem = pp.stem  # filename without extension
        ext = pp.suffix.lower()

        # Only source code files need paired tests
        if ext not in _SOURCE_EXTS or stem in _BOILERPLATE_STEMS:
            continue

        # Detect test files by convention (language-agnostic: test_*, *_test, *.spec, *.test)
        is_test = (
            stem.startswith("test_")
            or stem.endswith("_test")
            or stem.endswith(".spec")
            or stem.endswith(".test")
        )

        if is_test:
            # Collect test stems from both NEW and MODIFY so existing test files count
            base = stem
            for prefix in ("test_",):
                if base.startswith(prefix):
                    base = base[len(prefix):]
            for suffix in ("_test", ".spec", ".test"):
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
            test_stems.add(base)
        elif action == "NEW":
            # Only NEW implementation files require a paired test step
            impl_files.append(path)

    gaps: List[str] = []
    for impl_path in impl_files:
        stem = PurePosixPath(impl_path).stem  # e.g. "search"
        if stem not in test_stems:
            gaps.append(
                f"[NEW] {impl_path} has no paired test file — "
                f"add a [NEW] or [MODIFY] step targeting a "
                f"test_{stem} file covering all public interfaces."
            )
    return gaps


def check_changelog_entry(runbook_content: str) -> List[str]:
    """Check that the runbook includes a CHANGELOG.md modification step.

    Uses a regex that looks specifically for a ``[MODIFY]`` or ``[NEW]``
    block header targeting ``CHANGELOG.md``, avoiding false positives from
    prose mentions of the word "CHANGELOG".

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    if _re.search(
        r"####\s+\[(NEW|MODIFY)\]\s+CHANGELOG\.md",
        runbook_content,
        _re.IGNORECASE,
    ):
        return []
    return [
        "No CHANGELOG.md step found — every story must document its change "
        "in CHANGELOG.md."
    ]


def check_license_headers(runbook_content: str) -> List[str]:
    """Check that every ``[NEW]`` source file step includes the project license header.

    Reads key phrases from ``.agent/templates/license_header.txt`` and verifies
    that each ``[NEW]`` source file block contains at least one of them.
    Falls back to checking for ``Copyright`` or ``LICENSE`` if the template
    is not found.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        List of gap strings (empty if requirement met).
    """
    # Non-source extensions that don't require license headers
    _NON_SOURCE_EXTS = {
        ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
        ".html", ".css", ".csv", ".xml", ".svg", ".lock", ".env",
    }

    # Read key phrases from the license header template
    from agent.core.config import config
    template_path = Path(config.templates_dir) / "license_header.txt" if config.templates_dir else Path(".agent/templates/license_header.txt")
    if template_path.exists():
        template_text = template_path.read_text()
        # Extract the first non-empty line as the key phrase to check for
        key_phrases = [
            line.strip()
            for line in template_text.splitlines()
            if line.strip()
        ][:3]  # First 3 non-empty lines are enough to identify the header
    else:
        key_phrases = ["Copyright", "LICENSE"]

    gaps: List[str] = []
    new_file_pattern = _re.compile(
        r"####\s+\[NEW\]\s+([^\n]+)\s*\n+```[^\n]*\n(.*?)```",
        _re.DOTALL | _re.IGNORECASE,
    )
    for m in new_file_pattern.finditer(runbook_content):
        path = m.group(1).strip()
        ext = PurePosixPath(path).suffix.lower()
        if ext in _NON_SOURCE_EXTS:
            continue
        body = m.group(2)
        if not any(phrase in body for phrase in key_phrases):
            gaps.append(
                f"[NEW] {path} is missing the project license header "
                f"(from .agent/templates/license_header.txt). "
                "Add the license block at the top of the file."
            )
    return gaps


# ── Deterministic Auto-Fixes ─────────────────────────────────────────────── #
# These functions patch runbook content directly — no AI call required.        #
# ────────────────────────────────────────────────────────────────────────────── #

# Map file extensions to their comment prefix for license header injection.
_COMMENT_PREFIXES: dict[str, str] = {
    ".py": "# ", ".rb": "# ", ".sh": "# ", ".bash": "# ", ".zsh": "# ",
    ".yaml": "# ", ".yml": "# ", ".r": "# ", ".pl": "# ", ".pm": "# ",
    ".ts": "// ", ".js": "// ", ".tsx": "// ", ".jsx": "// ",
    ".go": "// ", ".rs": "// ", ".java": "// ", ".kt": "// ",
    ".c": "// ", ".cpp": "// ", ".h": "// ", ".hpp": "// ",
    ".cs": "// ", ".swift": "// ", ".scala": "// ", ".dart": "// ",
}


def auto_fix_license_headers(runbook_content: str) -> str:
    """Inject the project license header into ``[NEW]`` source file blocks.

    Reads the header from ``.agent/templates/license_header.txt``, wraps it
    with the appropriate comment prefix for the file's language, and prepends
    it to every ``[NEW]`` code block that is missing it.

    This is fully deterministic — no AI call is made.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Patched runbook content with license headers injected.
    """
    _NON_SOURCE_EXTS = {
        ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
        ".html", ".css", ".csv", ".xml", ".svg", ".lock", ".env",
    }

    from agent.core.config import config
    template_path = Path(config.templates_dir) / "license_header.txt" if config.templates_dir else Path(".agent/templates/license_header.txt")
    if not template_path.exists():
        return runbook_content  # nothing to inject

    raw_header = template_path.read_text().rstrip("\n")

    # Read key phrases for presence check (same as check_license_headers)
    key_phrases = [
        line.strip()
        for line in raw_header.splitlines()
        if line.strip()
    ][:3]

    new_file_pattern = _re.compile(
        r"(####\s+\[NEW\]\s+([^\n]+)\s*\n+)(```[^\n]*\n)(.*?```)",
        _re.DOTALL | _re.IGNORECASE,
    )

    def _inject(m: _re.Match) -> str:
        header_line = m.group(1)  # #### [NEW] path\n\n
        fence_open = m.group(3)    # ```lang\n
        body_and_close = m.group(4)  # code...```
        path = m.group(2).strip()

        ext = PurePosixPath(path).suffix.lower()
        if ext in _NON_SOURCE_EXTS:
            return m.group(0)

        # Already has the header?
        if any(phrase in body_and_close for phrase in key_phrases):
            return m.group(0)

        prefix = _COMMENT_PREFIXES.get(ext, "# ")
        formatted_header = "\n".join(
            f"{prefix}{line}".rstrip() for line in raw_header.splitlines()
        ) + "\n\n"

        return header_line + fence_open + formatted_header + body_and_close

    return new_file_pattern.sub(_inject, runbook_content)


def auto_fix_changelog_step(runbook_content: str) -> str:
    """Append a ``[MODIFY] CHANGELOG.md`` step if one is missing.

    This is fully deterministic — no AI call is made.

    Args:
        runbook_content: Raw runbook markdown.

    Returns:
        Patched runbook content with changelog step appended if needed.
    """
    if _re.search(
        r"####\s+\[(NEW|MODIFY)\]\s+CHANGELOG\.md",
        runbook_content,
        _re.IGNORECASE,
    ):
        return runbook_content  # already present

    changelog_step = (
        "\n\n### Step N: Update CHANGELOG\n"
        "#### [MODIFY] CHANGELOG.md\n\n"
        "Add an entry under the `[Unreleased]` section documenting this change.\n"
    )
    return runbook_content.rstrip() + changelog_step


def check_otel_spans(runbook_content: str, story_content: str) -> List[str]:
    """Check that runbook steps touching commands/ or core/ include OTel spans.

    Only applies when the story explicitly mentions observability, tracing,
    or a new flow in commands/ or core/.

    Args:
        runbook_content: Raw runbook markdown.
        story_content: Raw story markdown (used to detect observability AC).

    Returns:
        List of gap strings (empty if requirement met or not applicable).
    """
    otel_keywords = ("opentelemetry", "otel", "tracing", "span", "observability")
    if not any(kw in story_content.lower() for kw in otel_keywords):
        return []

    if "start_as_current_span" in runbook_content or "tracer.start" in runbook_content:
        return []

    touches_infra = _re.search(
        r"####\s+\[(NEW|MODIFY)\]\s+\.agent/src/agent/(commands|core)/",
        runbook_content,
        _re.IGNORECASE,
    )
    if touches_infra:
        return [
            "Story requires OTel observability but no 'start_as_current_span' / "
            "'tracer.start' found in runbook steps touching commands/ or core/. "
            "Add an OTel span for the new flow."
        ]
    return []


def build_dod_correction_prompt(
    gaps: List[str],
    story_content: str,
    acs: List[str],
) -> str:
    """Build a targeted correction prompt that bundles all DoD gaps.

    Args:
        gaps: List of gap description strings from the deterministic checkers.
        story_content: Scrubbed story text (for AC context).
        acs: Extracted acceptance criteria list.

    Returns:
        Formatted instruction string ready to append to the AI user prompt.
    """
    lines = [
        "DOD COMPLIANCE GATE FAILED. The following requirements are missing "
        "from the generated runbook:\n"
    ]
    for i, gap in enumerate(gaps, 1):
        lines.append(f"  {i}. {gap}")

    if acs:
        lines.append(
            "\nACCEPTANCE CRITERIA FROM STORY (ensure ALL are addressed by at "
            "least one Implementation Step):"
        )
        for ac in acs:
            lines.append(f"  - {ac}")

    lines.append(
        "\nInstruction: Regenerate the FULL runbook ensuring every gap above is "
        "resolved. Do not omit any existing correct steps — only add/fix the "
        "missing items. Return the complete updated runbook."
    )
    return "\n".join(lines)
