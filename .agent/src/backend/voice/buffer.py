
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
