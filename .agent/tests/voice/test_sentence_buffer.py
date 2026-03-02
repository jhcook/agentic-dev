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


import pytest
from backend.voice.buffer import SentenceBuffer

async def list_to_stream(items: list):
    """Helper to simulate async generator from list."""
    for item in items:
        yield item
        # Simulate slight delay optional
        # await asyncio.sleep(0.001)

@pytest.mark.asyncio
async def test_buffer_simple_sentence():
    buffer = SentenceBuffer()
    tokens = ["Hello", " ", "world", "."]
    
    stream = buffer.process(list_to_stream(tokens))
    result = [s async for s in stream]
    
    # Should yield one sentence
    assert len(result) == 1
    assert result[0] == "Hello world."
    # Wait, my split logic in buffer.py:
    # re.split includes delimiters if captured?
    # self.sentence_end_pattern = re.compile(r'(?<=[.?!])\s+')
    # Split occurs AFTER the punctuation due to lookbehind.
    # So "Hello world. " -> "Hello world."
    assert result[0] == "Hello world."

@pytest.mark.asyncio
async def test_buffer_multiple_sentences():
    buffer = SentenceBuffer()
    tokens = ["One", ".", " ", "Two", "!", " ", "Three", "?"]
    
    stream = buffer.process(list_to_stream(tokens))
    result = [s async for s in stream]
    
    assert len(result) == 3
    assert result[0] == "One."
    assert result[1] == "Two!"
    assert result[2] == "Three?"

@pytest.mark.asyncio
async def test_buffer_incomplete_flush():
    buffer = SentenceBuffer()
    tokens = ["Incomplete", " ", "sentence"]
    # No punctuation
    
    stream = buffer.process(list_to_stream(tokens))
    result = [s async for s in stream]
    
    # Needs to flush at end
    assert len(result) == 1
    assert result[0] == "Incomplete sentence"

@pytest.mark.asyncio
async def test_buffer_streaming_behavior():
    buffer = SentenceBuffer()
    tokens = ["First", ".", " ", "Sec", "ond", "."]
    
    result = []
    async for sentence in buffer.process(list_to_stream(tokens)):
        result.append(sentence)
        
    assert result == ["First.", "Second."]
