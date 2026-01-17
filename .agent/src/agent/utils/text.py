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

"""Text utilities for Mermaid diagram generation and other text processing."""


def sanitize_mermaid_label(text: str) -> str:
    """
    Sanitize a string for safe use as a Mermaid diagram node label.
    
    Mermaid labels are enclosed in quotes. This function escapes characters
    that have special meaning in Mermaid's label syntax to prevent rendering
    issues or syntax errors.
    
    Args:
        text: The raw text to sanitize.
        
    Returns:
        A sanitized string safe for use in Mermaid label syntax.
        
    Examples:
        >>> sanitize_mermaid_label('Simple text')
        'Simple text'
        >>> sanitize_mermaid_label('Text with "quotes"')
        'Text with #quot;quotes#quot;'
    """
    if not text:
        return ""
    
    # Escape double quotes with Mermaid HTML entity
    text = text.replace('"', '#quot;')
    
    # Escape ampersand (causes syntax errors in Mermaid)
    text = text.replace('&', '&amp;')
    
    # Escape angle brackets that could interfere with HTML-like syntax
    text = text.replace('<', '#lt;')
    text = text.replace('>', '#gt;')
    
    # Escape pipe character used for node shapes
    text = text.replace('|', '#124;')
    
    return text
