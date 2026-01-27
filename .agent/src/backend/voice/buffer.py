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
    """
    def __init__(self):
        self.buffer = ""
        # Split on ., ?, !, or newline, keeping the delimiter.
        # This regex looks for these chars followed by space or end of string.
        self.sentence_end_pattern = re.compile(r'(?<=[.?!])\s+')

    async def process(self, token_stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
        """
        Consumes a stream of tokens and yields full sentences, 
        automatically skipping technical noise and code blocks.
        """
        async for token in token_stream:
            self.buffer += token
            
            # 1. Strip ALL complete code blocks immediately.
            self.buffer = re.sub(r'```[\s\S]*?```', ' ', self.buffer)
            
            # 2. Check for an incomplete block.
            parts = self.buffer.split('```')
            if len(parts) % 2 == 0:
                process_limit = len(self.buffer) - len(parts[-1]) - 3
                text_to_process = self.buffer[:process_limit]
                remainder = self.buffer[process_limit:] # Starts with ```
            else:
                text_to_process = self.buffer
                remainder = ""

            # 3. Check for full segments (including newlines as break-points for logs)
            # We treat newlines as hard sentence breaks for technical data.
            sentences = re.split(r'(?<=[.?!])\s+|\n', text_to_process)
            
            if len(sentences) > 1:
                # All except last are complete
                for s in sentences[:-1]:
                    if self._is_speakable(s):
                        yield s.strip()
                
                self.buffer = sentences[-1] + remainder
            else:
                pass        

        # End of stream: yield whatever is left, BUT FILTER IT
        final = self.buffer.strip()
        if final and self._is_speakable(final):
            yield final
            
        self.buffer = ""

    def _is_speakable(self, text: str) -> bool:
        """
        Aggressive heuristic to skip technical noise, logs, and structured data.
        """
        s = text.strip()
        if not s: return False
        
        # 1. Skip code block markers
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
        if ': ' in s and not any(c in s for c in '.?!'): # Key-value pair without punctuation
            return False

        # 7. No ASCII letters (only symbols/numbers)
        if not any(c.isalpha() for c in s): return False

        return True
