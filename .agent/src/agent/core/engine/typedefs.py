from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

@dataclass
class AgentAction:
    tool: str
    tool_input: Dict[str, Any]
    log: str  # The raw "Thought" leading to this action

@dataclass
class AgentObservation:
    output: str  # The result from the tool

@dataclass
class AgentFinish:
    return_values: Dict[str, Any]
    log: str

@dataclass
class AgentStep:
    action: AgentAction
    observation: AgentObservation
