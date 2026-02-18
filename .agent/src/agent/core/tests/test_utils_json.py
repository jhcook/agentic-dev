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

import json
from agent.core.utils import extract_json_from_response

def test_extract_json_standard_block():
    response = """Here is the JSON:
```json
[
    {"id": 1}
]
```
Hope this helps."""
    result = extract_json_from_response(response)
    assert result.strip() == '[\n    {"id": 1}\n]'

def test_extract_json_no_block():
    response = """
    [
        {"id": 2}
    ]
    """
    result = extract_json_from_response(response)
    assert '{"id": 2}' in result

def test_extract_json_trailing_noise_with_brackets():
    # This was the failure case: regex captured until the last ']'
    response = """[{"id": 3}] Some text [info] more text."""
    result = extract_json_from_response(response)
    assert result == '[{"id": 3}]'

def test_extract_json_nested_arrays():
    response = """[[1, 2], [3, 4]]"""
    result = extract_json_from_response(response)
    assert result == "[[1, 2], [3, 4]]"

def test_extract_json_thinking_block():
    response = """<thinking>
I should return a list of options.
</thinking>
```json
[
  {"title": "Fix"}
]
```"""
    result = extract_json_from_response(response)
    assert "Fix" in result

def test_extract_json_malformed_fallback():
    # If no valid JSON found, it should return likely the list match or original
    response = "[This is not json]"
    # It tries to parse, fails, and falls back to regex match
    result = extract_json_from_response(response)
    assert result == "[This is not json]"

def test_extract_json_multiple_blocks_trailing():
    # It should find the valid block even if there is trailing stuff
    response = """
    [{"a": 1}]
    
    Ignore this [b]
    """
    result = extract_json_from_response(response)
    assert '{"a": 1}' in result

def test_extract_json_lenient_newlines():
    # Test strict=False support (unescaped newlines in strings)
    response = """
    [
        {
            "description": "Line 1
Line 2"
        }
    ]
    """
    result = extract_json_from_response(response)
    # Checks that we got an array, not the empty string or raw logic
    assert result.strip().startswith("[")
    assert result.strip().endswith("]")
    assert "Line 1" in result
    # Ensure it parses with strict=False
    parsed = json.loads(result, strict=False)
    assert len(parsed) == 1
    assert "Line 1\nLine 2" in parsed[0]["description"]
