# Parser and Assembly Engine API Usage

This guide demonstrates how to programmatically manipulate runbook skeletons using the `agent.core.implement` module.

## Parsing a Skeleton

The `parser.py` module converts raw text into a `RunbookSkeleton` object containing `RunbookBlock` instances.

```python
from agent.core.implement.parser import parse_skeleton

raw_content = """
<!-- block: header -->
# System Update
<!-- /block -->
"""

skeleton = parse_skeleton(raw_content)
block = skeleton.get_block("header")
print(f"Found block: {block.id} with content: {block.content}")
```

## Copyright

Copyright 2026 Justin Cook. Licensed under the Apache License, Version 2.0.
