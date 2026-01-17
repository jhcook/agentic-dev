"""Dependency analysis for impact assessment."""

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

import ast
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set


class DependencyAnalyzer:
    """Analyzes code dependencies using AST for Python and regex for JS."""
    
    def __init__(self, repo_root: Path):
        """
        Initialize the dependency analyzer.
        
        Args:
            repo_root: Root directory of the repository
        """
        self.repo_root = repo_root
    
    def analyze_python_imports(self, file_path: Path) -> Set[str]:
        """
        Parse Python imports using AST (handles all import patterns).
        
        Args:
            file_path: Absolute path to Python file
            
        Returns:
            Set of imported module names (e.g., 'agent.core.utils')
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            return set()
        
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        
        return imports
    
    def analyze_js_imports(self, file_path: Path) -> Set[str]:
        """
        Parse JavaScript/TypeScript imports using regex.
        
        Handles ES6 and CommonJS patterns.
        
        Args:
            file_path: Absolute path to JS/TS file
            
        Returns:
            Set of imported file paths (relative or absolute)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, FileNotFoundError):
            return set()
        
        imports = set()
        
        # ES6: import ... from 'path'
        es6_pattern = r"import\s+(?:[\w\s{},*]+\s+from\s+)?['\"]([^'\"]+)['\"]"
        imports.update(re.findall(es6_pattern, content))
        
        # CommonJS: require('path')
        cjs_pattern = r"require\(['\"]([^'\"]+)['\"]\)"
        imports.update(re.findall(cjs_pattern, content))
        
        return imports
    
    def resolve_python_module_to_file(self, module_name: str) -> Optional[Path]:
        """
        Convert Python module name to file path.
        
        Examples:
            'agent.core.utils' -> '.agent/src/agent/core/utils.py'
            'agent.core' -> '.agent/src/agent/core/__init__.py'
            
        Args:
            module_name: Python module name (e.g., 'agent.core.utils')
            
        Returns:
            Path relative to repo root, or None if not found
        """
        parts = module_name.split('.')
        
        # Try as a file
        file_path = self.repo_root / '.agent' / 'src' / '/'.join(parts)
        if file_path.with_suffix('.py').exists():
            return file_path.with_suffix('.py').relative_to(self.repo_root)
        
        # Try as a package
        init_path = file_path / '__init__.py'
        if init_path.exists():
            return init_path.relative_to(self.repo_root)
        
        return None
    
    def resolve_js_import_to_file(
        self, import_path: str, from_file: Path
    ) -> Optional[Path]:
        """
        Resolve JavaScript import to actual file path.
        
        Handles relative imports and common extensions.
        
        Args:
            import_path: Import string (e.g., './utils' or '../components')
            from_file: File containing the import (relative to repo root)
            
        Returns:
            Path relative to repo root, or None if not found
        """
        # Skip node_modules
        if not import_path.startswith('.'):
            return None
        
        from_dir = (self.repo_root / from_file).parent
        target = (from_dir / import_path).resolve()
        
        # Try common extensions
        for ext in ['.js', '.ts', '.tsx', '.jsx']:
            if target.with_suffix(ext).exists():
                try:
                    return target.with_suffix(ext).relative_to(self.repo_root)
                except ValueError:
                    return None
        
        # Try as directory with index file
        for ext in ['.js', '.ts', '.tsx']:
            index_file = target / f'index{ext}'
            if index_file.exists():
                try:
                    return index_file.relative_to(self.repo_root)
                except ValueError:
                    return None
        
        return None
    
    @lru_cache(maxsize=1000)
    def get_file_dependencies(self, file_path: Path) -> Set[Path]:
        """
        Get all files that this file imports (cached for performance).
        
        Args:
            file_path: File to analyze (relative to repo root)
            
        Returns:
            Set of Path objects relative to repo root
        """
        dependencies = set()
        abs_path = self.repo_root / file_path
        
        if file_path.suffix == '.py':
            module_names = self.analyze_python_imports(abs_path)
            for module in module_names:
                resolved = self.resolve_python_module_to_file(module)
                if resolved:
                    dependencies.add(resolved)
        
        elif file_path.suffix in ['.js', '.ts', '.tsx', '.jsx']:
            import_paths = self.analyze_js_imports(abs_path)
            for imp in import_paths:
                resolved = self.resolve_js_import_to_file(imp, file_path)
                if resolved:
                    dependencies.add(resolved)
        
        return dependencies
    
    def find_reverse_dependencies(
        self, changed_files: List[Path], all_files: List[Path]
    ) -> Dict[Path, Set[Path]]:
        """
        Find which files depend on the changed files.
        
        Args:
            changed_files: Files that were modified
            all_files: All files in the repo to check
        
        Returns:
            Dict mapping changed file -> set of files that import it
        """
        start_time = time.time()
        reverse_deps: Dict[Path, Set[Path]] = {f: set() for f in changed_files}
        changed_set = set(changed_files)
        
        for file in all_files:
            if file in changed_set:
                continue
            
            try:
                deps = self.get_file_dependencies(file)
                for dep in deps:
                    if dep in changed_set:
                        reverse_deps[dep].add(file)
            except Exception:
                # Skip files that can't be parsed
                continue
        
        duration = time.time() - start_time
        if duration > 5.0:
            print(f"⚠️  Dependency analysis took {duration:.2f}s")
        
        return reverse_deps
