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
        Consumes a stream of tokens and yields full sentences.
        
        Args:
            token_stream: Async generator yielding strings (tokens/chunks).
            
        Yields:
            Complete sentences as strings.
        """
        async for token in token_stream:
            self.buffer += token
            
            # Check if we have a full sentence
            sentences = self.sentence_end_pattern.split(self.buffer)
            
            # If we have more than 1 split, it means we found delimiters.
            # The last element is the incomplete remainder (buffer).
            if len(sentences) > 1:
                # All except last are complete sentences
                for sentence in sentences[:-1]:
                    sentence = sentence.strip()
                    if sentence:
                        yield sentence
                
                # Keep the remainder
                self.buffer = sentences[-1]
        
        # End of stream: yield whatever is left
        if self.buffer.strip():
            yield self.buffer.strip()
            self.buffer = ""
