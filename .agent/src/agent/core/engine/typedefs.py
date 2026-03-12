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

from dataclasses import dataclass
from typing import Any, Dict, Union
from pydantic import BaseModel, Field

class AgentAction(BaseModel):
    """
    Represents a decision by the agent to execute a tool.
    
    Attributes:
        tool: The name of the tool to execute.
        tool_input: A dictionary representing the tool arguments, or a primary string argument.
        log: The raw 'Thought' string that immediately preceded this Action.
    """
    tool: str
    tool_input: Union[Dict[str, Any], str]
    log: str  # The raw "Thought" leading to this action
    
    model_config = {"extra": "forbid"}

@dataclass
class AgentObservation:
    output: str  # The result from the tool

class AgentFinish(BaseModel):
    """
    Represents the final answer produced by the agent terminating the execution loop.
    
    Attributes:
        return_values: A dictionary containing the final output.
        log: The raw final generated text output.
    """
    return_values: Dict[str, Any]
    log: str
    
    model_config = {"extra": "forbid"}

@dataclass
class AgentStep:
    action: AgentAction
    observation: AgentObservation
