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
from typing import AsyncGenerator, List 

class SentenceBuffer:
    """
    Buffers text tokens and yields full sentences.
    Designed for use in an async streaming pipeline.
    State aware to suppress code blocks.
    """
    def __init__(self):
        self.buffer = ""
        self.in_code_block = False
        self.sentence_end_pattern = re.compile(r'(?<=[.?!])\s+')

    async def process(self, token_stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        """
        Consumes a stream of tokens and yields full sentences.
        Suppresses content within markdown code blocks (``` ... ```).
        """
        async for token in token_stream:
            # 1. Handle Code Block Toggling
            # We process token by token or small chunks.
            # If we see ``` and we are NOT in block, we enter block.
            # If we see ``` and we ARE in block, we exit block.
            
            # Simple approach: Check for marker in token (or buffer accumulation)
            self.buffer += token
            
            # Check for toggle markers
            while '```' in self.buffer:
                # Found a marker.
                before, _, after = self.buffer.partition('```')
                
                if not self.in_code_block:
                    # We were OUT, now entering IN.
                    # 'before' is valid text. Yield it if it forms sentences.
                    if before:
                        # Process 'before' as valid text
                        for s in self._extract_sentences(before):
                             yield s
                    
                    # We are now IN code block. 
                    self.in_code_block = True
                    self.buffer = after # Continue processing 'after' with new state
                else:
                    # We were IN, now exiting OUT.
                    # 'before' is code content. DISCARD IT.
                    # We are now OUT of code block.
                    self.in_code_block = False
                    self.buffer = after # Continue processing 'after'
            
            if self.in_code_block:
                # If inside a code block, discard content but safeguard potential markers
                if len(self.buffer) > 3:
                     # Keep trailing backticks just in case it's the start of a marker
                     stripped = self.buffer.rstrip('`')
                     backticks = self.buffer[len(stripped):]
                     self.buffer = backticks
            else:
                # We are OUT side. 'buffer' contains potentially valid text.
                # Extract complete sentences.
                completed_sentences, remainder = self._split_sentences_robust(self.buffer)
                for s in completed_sentences:
                    if self._is_speakable(s):
                        yield s
                self.buffer = remainder

        # End of stream
        if not self.in_code_block and self.buffer:
            if self._is_speakable(self.buffer):
                yield self.buffer.strip()
            
        self.buffer = ""
        self.in_code_block = False

    def _split_sentences_robust(self, text: str):
        """Splits text into [complete_sentences], remainder."""
        # Split on [.?!] followed by space or newline
        parts = re.split(r'(?<=[.?!])\s+', text)
        if len(parts) == 1:
            return [], parts[0]
            
        return parts[:-1], parts[-1]

    def _extract_sentences(self, text: str):
        """Yields speakable sentences from a closed chunk of text."""
        sentences = re.split(r'(?<=[.?!])\s+|\n', text)
        for s in sentences:
            s_stripped = s.strip()
            if s_stripped and self._is_speakable(s_stripped):
                yield s_stripped

    def _is_speakable(self, text: str) -> bool:
        """
        Aggressive heuristic to skip technical noise, logs, and structured data.
        """
        s = text.strip()
        if not s: return False
        
        # 1. Skip code block markers (redundant but safe)
        if '```' in s: return False
            
        # 2. Git Status patterns (e.g., "M path/to/file")
        if re.match(r'^[MADRCU\?G\s]{1,3}\s+[\.\w/-]+$', s): return False
        
        # 3. Terminal Command patterns (starts with $, >, or looks like a command)
        if s.startswith('$ ') or s.startswith('> '): return False
        if re.match(r'^[\w-]+(\s+--?[\w-]+)+', s): return False # Command with flags
        
        # 4. Path patterns (multiple separators, no spaces)
        if s.count('/') >= 2 and ' ' not in s: return False
        if s.count('\\') >= 2 and ' ' not in s: return False
            
        # 5. File Lists (all words have extensions or separators)
        words = s.split()
        if len(words) > 2 and all(re.search(r'[\./\\]', w) for w in words):
            return False
            
        # 6. JSON / YAML detection
        if s.startswith('{') and s.endswith('}'): return False
        if s.startswith('[') and s.endswith(']'): return False
        if ': ' in s and not any(c in s for c in '.?!'): # Key-value pair
            return False

        # 7. No ASCII letters (only symbols/numbers)
        if not any(c.isalpha() for c in s): return False

        return True
