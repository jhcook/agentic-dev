---
description: Perform impact analysis on code changes using the Agent's AI capabilities.
---

# Workflow: Impact Analysis

You will manually perform the impact analysis logic using both static dependency analysis and AI insights.

## PROCESS

1. **Identify Story ID**:
   - Determine the Story ID from the context or user input.

2. **Get Git Diff**:
   - If a base branch is provided (e.g., via User Request "compare against main"), run:
     `git diff <BASE>...HEAD .`
   - Otherwise, get the staged changes:
     `git diff --cached .`
   - If the output is empty, notify the user.

3. **Read Story Context**:
   - Locate the story file: `.agent/cache/stories/*/<STORY-ID>*.md`.
   - Read its content using `view_file`.

4. **Perform Static Dependency Analysis**:
   - Import and use the `DependencyAnalyzer` class:
     ```python
     from pathlib import Path
     from agent.core.dependency_analyzer import DependencyAnalyzer
     
     repo_root = Path.cwd()
     analyzer = DependencyAnalyzer(repo_root)
     
     # Convert changed files to Path objects
     changed_files = [Path(f) for f in files_from_diff]
     
     # Get all Python and JS files
     all_files = []
     for pattern in ['**/*.py', '**/*.js', '**/*.ts', '**/*.tsx']:
         all_files.extend(repo_root.glob(pattern))
     all_files = [f.relative_to(repo_root) for f in all_files]
     
     # Find reverse dependencies
     reverse_deps = analyzer.find_reverse_dependencies(changed_files, all_files)
     total_impacted = sum(len(deps) for deps in reverse_deps.values())
     ```
   - Display the dependency analysis results showing which files depend on the changes.

5. **Generate AI Analysis**:
   - Construct a prompt including:
     - **Story Content**
     - **Git Diff**
     - **Dependency Analysis Results** (from step 4)
   - **PROMPT**:
     ```
     You are an expert Release Engineer. Analyze these changes:
     
     STORY:
     <Story Content>
     
     DIFF:
     <Git Diff>
     
     DEPENDENCY ANALYSIS:
     - Total files changed: <count>
     - Total files impacted (reverse dependencies): <total_impacted>
     - Detailed dependencies:
       <list of changed files and their dependents>
     
     Determine:
     1. Components touched (based on file paths and dependencies)
     2. Workflows affected (based on dependency tree)
     3. Risks:
        - Security: Any auth, validation, or data handling changes?
        - Performance: Large dependency trees indicate high blast radius
        - Reliability: Changes to heavily-depended-on files are higher risk
     4. Breaking Changes: API changes, signature changes, removed exports
     
     Provide a comprehensive "Impact Analysis Summary" that combines:
     - The static dependency data
     - Your AI analysis of risks and breaking changes
     ```

6. **Update Story (Optional)**:
   - If the user requested to update the story (e.g., "update the story"), use `replace_file_content` to inject the analysis into the "Impact Analysis Summary" section of the story file.
   - Include both dependency metrics and AI insights.

7. **Report**:
   - Output the combined analysis to the user:
     - Static dependency analysis results
     - AI-generated risk assessment
     - Recommendations

## NOTES:
- Do NOT run git commit.
- Do NOT modify files unless explicitly requested via "update the story".
- Focus on providing actionable insights combining static analysis and AI reasoning.
- The dependency analysis provides objective data; AI adds context and risk assessment.