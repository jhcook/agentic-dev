#!/usr/bin/env python3
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

import os
import subprocess
import chardet
from typing import List


def get_all_python_files(repo_path: str) -> List[str]:
    result = subprocess.run(
        ['find', repo_path, '-name', '*.py', '-print0'],
        capture_output=True,
        text=True,
        check=True
    )
    files = result.stdout.split('\x00')
    files = [f for f in files if f]
    files = [f for f in files if '.venv' not in f]
    return files


def get_files_with_copyright(repo_path: str) -> List[str]:
    result = subprocess.run(
        ['grep', '-l', 'Copyright 2026 Justin Cook', '-r', repo_path],
        capture_output=True,
        text=True,
        check=True
    )
    files = result.stdout.splitlines()
    return files


def is_text_file(filepath: str) -> bool:
    try:
        with open(filepath, 'rb') as f:
            rawdata = f.read()
            result = chardet.detect(rawdata)
            encoding = result['encoding']
            if encoding is None:
                return False
            with open(filepath, 'r', encoding=encoding) as f:
                f.read()
            return True
    except:
        return False


def add_license_header(filepath: str, license_header: str) -> None:
    try:
        with open(filepath, 'r+') as f:
            content = f.read()
            f.seek(0, 0)
            f.write(license_header.rstrip('\n') + '\n\n' + content)
    except Exception as e:
        print(f"Error adding license to {filepath}: {e}")

if __name__ == "__main__":
    repo_path = os.getcwd()
    all_files = get_all_python_files(repo_path)
    files_with_copyright = get_files_with_copyright(repo_path)
    files_without_copyright = [f for f in all_files if f not in files_with_copyright]

    license_header = '''# Copyright 2026 Justin Cook
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
# limitations under the License.'''

    for filepath in files_without_copyright:
        if is_text_file(filepath):
            print(f"Adding license to {filepath}")
            add_license_header(filepath, license_header)
        else:
            print(f"Skipping binary file: {filepath}")