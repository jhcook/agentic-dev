## STORY-ID: INFRA-036: Voice Agent Tool Integration

## State

ACCEPTED

## Goal Description

Enhance the VoiceOrchestrator with tool support, persistent memory, configurable prompts, latency handling, safety mechanisms, and observability, enabling developers to create more sophisticated and useful voice interactions.

## Panel Review Findings

- **@Architect**: The plan is sound. Decoupling tool definitions from the Orchestrator is crucial. The use of `LangGraph` is a good choice. We should explore other graph-based frameworks if needed for complexity. `SqliteSaver` is a reasonable starting point. Consider scalability implications as the agent's user base grows. Should evaluate alternatives (Postgres, Redis) for long-term persistence. Need to detail the Tool definition and interface more concretely.
- **@Security**: Sandboxing is critical. Ensure `lookup_documentation` and any other tools cannot be abused for arbitrary code execution or data exfiltration. Validate user input thoroughly before passing it to the tools. The verbal confirmation for sensitive tools is a good first step. Implement rate limiting and usage quotas. Must prevent prompt injection attacks via the configurable prompt. The file system access limitations should be very specific and easily auditable. Tools should run with the least privilege necessary.
- **@QA**: We need to define clear test cases for each tool, covering both success and failure scenarios. Boundary conditions for tool inputs should be tested. The latency handling with "Thinking..." audio should be tested under varying network conditions and tool execution times. Consider using synthetic speech to test voice agent responses to a controlled set of tool outputs. Must have negative test cases for the safety confirmation mechanism.
- **@Docs**: The implementation requires updating the README to describe how to configure and use tools with the VoiceOrchestrator. Example configurations and tool definitions should be provided. The format for the system prompt via `agent config` needs to be documented clearly. Any changes to the API need corresponding documentation in the OpenAPI spec (though this seems more backend).
- **@Compliance**: Ensure compliance with data privacy regulations (e.g., GDPR, CCPA) when storing conversation history. User consent for data retention should be obtained. Anonymization or pseudonymization techniques should be considered for sensitive data. Validate the "sensitive tools" list is maintained, and that access is logged for audit purposes.
- **@Observability**: We need to define specific metrics for tool execution duration, frequency of tool usage, and any errors encountered during tool execution. The arguments passed to each tool should be logged (with appropriate redaction of sensitive information). The system prompt needs to be included in the logs for debugging purposes. Define alerting thresholds for tool latency and error rates. Structured logging must be enforced.

## Implementation Steps

### backend/voice/orchestrator.py

#### MODIFY backend/voice/orchestrator.py

- Import necessary libraries for LangGraph, SqliteSaver, and tool execution.
- Replace the basic conversational agent with a LangGraph agent configured with tools.
- Initialize `SqliteSaver` to persist conversation history in `.agent/storage/`.
- Implement the logic for playing "Thinking..." audio/sound during long tool execution.
- Add logging for tool execution duration, arguments, and results.
- Integrate with OpenTelemetry/LogBus for tracing tool execution.

```python
# Example (Conceptual - Adapt to your actual code)
from langgraph.prebuilt import ToolExecutor, create_agent_executor
from langchain_community.tools import Tool
from langchain_community.utilities import SerpAPIWrapper
from langchain_core.runnables import chain
from langchain_community.chat_models import ChatOpenAI
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.tools import DuckDuckGoSearchRun
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from langchain_community.callbacks import get_openai_callback
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.embeddings import OpenAIEmbeddings
from langchain_community.llms import OpenAI

from langchain.prompts import PromptTemplate

import logging
import time
import os
from langchain_community.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain.embeddings import OpenAIEmbeddings
from langchain_community.llms import OpenAI
from langchain.prompts import PromptTemplate

# Example tool definition
def lookup_documentation(query: str) -> str:
    """Searches the documentation for a given query."""
    # Implement your documentation lookup logic here.
    # This is a placeholder.  Consider using a vector store.
    return f"Documentation search results for: {query} (Placeholder)"

# Initialize SqliteSaver (adjust path as needed)
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.memory import ChatMessageHistory
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import CharacterTextSplitter

from langchain.prompts import PromptTemplate

from dotenv import load_dotenv

from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain.schema import SystemMessage
from langchain.agents import AgentExecutor, create_react_agent

# Load all documents from the specified directory
def load_documents(directory):
    documents = []
    # Check if the directory exists
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        return documents

    # Iterate over all files in the directory
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)

        # Check if it's a file and has a supported extension
        if os.path.isfile(filepath) and filename.endswith('.md'):
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    text = file.read()
                    metadata = {"source": filename}  # Store the filename as the source
                    documents.append((text, metadata))
            except Exception as e:
                print(f"Error reading file {filename}: {e}")
        else:
            print(f"Skipped file: {filename} (not a supported format or not a file)")

    if not documents:
        print("No documents were loaded. Please check the directory and file formats.")
    return documents

# Split documents into chunks
def split_documents(documents, chunk_size=1000, chunk_overlap=100):
    text_splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunked_documents = []
    for doc, metadata in documents:
        split_docs = text_splitter.split_text(doc)
        for chunk in split_docs:
             chunked_documents.append(chunk)
    return chunked_documents

def create_vector_store(chunked_documents):
    # OpenAIEmbeddings will automatically read the API key from the .env file
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma.from_texts(
        chunked_documents,
        embedding=embeddings
    )
    return vector_store

def run_documentation_chain(user_query):
    docs_dir = os.path.abspath(os.path.join(os.path.dirname( __file__ ), '..', '..', 'docs')) # This will point to the root 'docs' directory
    documents = load_documents(docs_dir)
    chunked_documents = split_documents(documents)
    vector_store = create_vector_store(chunked_documents)
    retriever = vector_store.as_retriever()
    template = """You are a helpful assistant that answers user queries about documentation for a software agent.
    Given the following context, answer the query:
    {context}

    Query: {question}
    """
    prompt = PromptTemplate.from_template(template)
    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | OpenAI()
        | StrOutputParser()
    )
    response = chain.invoke(user_query)
    return response

class SafeTool(Tool):
    """Tool that requires verbal confirmation before execution."""
    requires_confirmation: bool = True

tools = [
    Tool(
        name = "lookup_documentation",
        func = run_documentation_chain, #lookup_documentation,
        description="Useful for when you need to lookup documentation." # should we provide more data to this?
    )
]


tool_executor = ToolExecutor(tools=tools)


template = """You are a voice assistant that can lookup documentation, answer questions, etc.
You have access to the following tools:

{tools_description}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

{chat_history}

Question: {input}
{agent_scratchpad}"""

prompt = ChatPromptTemplate.from_messages([
    ("system", template),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

def get_openai_agent(template, tools, tool_executor):
    agent = (
        {
            "input": lambda x: x["input"],
            "tools_description": lambda x: "\n".join([f"{tool.name}: {tool.description}" for tool in tools]),
            "tool_names": lambda x: ", ".join([tool.name for tool in tools]),
            "chat_history": lambda x: x["chat_history"],
            "agent_scratchpad": lambda x: format_log_to_str(x['intermediate_steps']),
        }
        | prompt
        | ChatOpenAI(temperature=0)
        | OpenAIAgentOutputParser()
    )
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return agent_executor

def format_log_to_str(log):
    formatted_log = ""
    for i, step in enumerate(log):
        formatted_log += f"\nThought: {step[0].log}\n"
        formatted_log += f"Observation: {step[1]}\n"
    return formatted_log

from typing import List, Dict, Any
import json
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.outputs import ChatGenerationResult
from langchain_core.messages import BaseMessage
from langchain.agents import AgentOutputParser
from langchain.schema import OutputParserException
class OpenAIAgentOutputParser(AgentOutputParser):
    def get_format_instructions(self) -> str:
        return FORMAT_INSTRUCTIONS

    def parse(self, llm_output: str) -> Any:
        if "Final Answer:" in llm_output:
            return AgentFinish(
                {"output": llm_output.split("Final Answer:")[-1].strip()}, llm_output
            )
        try:
            action = get_action_and_action_input(llm_output)
        except Exception as e:
            raise OutputParserException(f"Could not parse LLM output: {llm_output}")
        return AgentAction(action["tool"], action["tool_input"], llm_output)

def get_action_and_action_input(text: str) -> Dict:
    try:
        # Extract tool and tool_input using regex
        tool = re.search(r"Action: (.*?)(?=\nAction Input:)", text, re.DOTALL).group(1).strip()
        tool_input = re.search(r"Action Input: (.*?)(?=\n|$)", text, re.DOTALL).group(1).strip()
        return {"tool": tool, "tool_input": tool_input}
    except Exception as e:
        raise OutputParserException(f"Could not parse LLM output: {text}")


import re

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], Field(json_schema_extra={"type": "array", "items": {"type": "object"}})]
    steps: Annotated[List[Dict[str, Any]], Field(json_schema_extra={"type": "array", "items": {"type": "object"}})]

from typing import TypedDict, List, Dict, Any
from typing_extensions import Annotated, TypeAlias
from langchain_core.messages import BaseMessage
from langchain.schema import AgentAction, AgentFinish
from langchain.memory import ConversationBufferMemory
from langgraph.prebuilt import FunctionRouter, ToolExecutor
from langchain.chains import LLMChain

from langchain_core.utils import StrOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.schema import SystemMessage
from langchain.agents import AgentExecutor, create_react_agent

def initialize_agent(
    llm,
    tools,
):
    """Initialize the agent."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful voice assistant that can use tools to answer questions. You have access to the following tools:\n\n{tool_descriptions}",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    # Define a function to format messages
    def format_messages(messages):
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted_messages.append(f"Human: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"Assistant: {msg.content}")
        return "\n".join(formatted_messages)
    tool_names = ", ".join([tool.name for tool in tools])
    tool_descriptions = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])
    # LLM chain
    llm_chain = LLMChain(
        llm=llm,
        prompt=prompt,
    )
    # Agent executor
    agent_executor = AgentExecutor.from_llm_and_tools(
        llm=llm,
        tools=tools,
        llm_chain=llm_chain,
    )
    return agent_executor


# Initialize the Langchain agent
def initialize_langchain_agent(llm, tools, system_prompt):
    # Define the prompts

    prompt_new = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    # Pass in the tools and tool names to the prompt
    prompt = prompt_new.partial(
        tool_names=", ".join([tool.name for tool in tools]),
        tools_description="\n".join([f"{tool.name}: {tool.description}" for tool in tools])
    )

    # Define the agent
    agent = (
        {
            "input": lambda x: x["input"],
            "chat_history": lambda x: x["chat_history"],
            "agent_scratchpad": lambda x: format_log_to_str(x['intermediate_steps']),
        }
        | prompt
        | llm
        | OpenAIAgentOutputParser()
    )
    return agent

from langchain_core.messages import BaseMessage
def get_agent(tools, llm, system_prompt):
    """Get the agent."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad")
    ])

    # Pass in the tools and tool names to the prompt
    prompt = prompt.partial(
        tool_names=", ".join([tool.name for tool in tools]),
        tools_description="\n".join([f"{tool.name}: {tool.description}" for tool in tools])
    )

    def format_log_to_str(log):
        formatted_log = ""
        for i, step in enumerate(log):
            formatted_log += f"\nThought: {step[0].log}\n"
            formatted_log += f"Observation: {step[1]}\n"
        return formatted_log
    # Define the agent
    agent = (
        {
            "input": lambda x: x["input"],
            "chat_history": lambda x: x["chat_history"],
            "agent_scratchpad": lambda x: format_log_to_str(x['intermediate_steps']),
        }
        | prompt
        | llm
        | OpenAIAgentOutputParser()
    )
    return agent
```

#### NEW .agent/storage/

- Create this directory and the SQLite database file within it.

```bash
mkdir -p .agent/storage/
# SQLite database file will be created by SqliteSaver
```

### backend/config.py

#### MODIFY backend/config.py

- Add configuration options for the system prompt.
- Add a method to update the system prompt via `agent config`.

```python
# Example (Conceptual - Adapt to your actual code)
class AgentConfig:
    system_prompt: str = "You are a helpful voice assistant."

    def update_system_prompt(self, new_prompt: str):
        self.system_prompt = new_prompt

# In your agent config code:
config = AgentConfig()
config.update_system_prompt("New system prompt from agent config")
```

### tools/lookup_documentation.py

#### NEW tools/lookup_documentation.py

- Create a new file to define the `lookup_documentation` tool.
- Implement the tool logic (e.g., searching a documentation database).

```python
# Example (Conceptual - Adapt to your actual code)
def lookup_documentation(query: str) -> str:
    """Searches the documentation for a given query."""
    # Implement your documentation lookup logic here.
    return f"Documentation search results for: {query} (Placeholder)"

```

### scripts/agent_config.py

#### NEW scripts/agent_config.py

- Create script for configuring agent.

```python
# Example (Conceptual - Adapt to your actual code)
# Example usage: python agent_config.py --system-prompt "Updated system prompt"

import argparse

from backend.config import AgentConfig

def main():
    parser = argparse.ArgumentParser(description="Configure the voice agent.")
    parser.add_argument("--system-prompt", type=str, help="The new system prompt for the agent.")

    args = parser.parse_args()

    config = AgentConfig() # Initialize AgentConfig

    if args.system_prompt:
        config.update_system_prompt(args.system_prompt) # Assuming config object has a method update_system_prompt
        print(f"System prompt updated to: {args.system_prompt}")
    else:
        print("No configuration options provided.")

if __name__ == "__main__":
    main()

```

## Verification Plan

### Automated Tests

- [ ] Unit test `lookup_documentation` tool with various queries.
- [ ] Unit test `SqliteSaver` to ensure conversation history is persisted correctly.
- [ ] Unit test the configuration update for the system prompt.
- [ ] Integration test: Mock tool execution and verify agent uses tool output in its response.
- [ ] Test safety confirmation with a mock "sensitive" tool.

### Manual Verification

- [ ] Verify that the "Thinking..." audio plays when a tool takes > 1s to execute.
- [ ] Test the VoiceOrchestrator with different system prompts.
- [ ] Verify that the conversation history is persisted across agent restarts.
- [ ] Test various tool interactions and verify the agent's responses.
- [ ] Trigger a "sensitive" tool and verify the verbal confirmation request.
- [ ] Check logs for tool execution duration, arguments, and results.
- [ ] **Transcript Sync**: Emit JSON events (User Text, Agent Text, Tool Result) over WebSocket to enable frontend chat history.
- [ ] **Latency Handling**: If tool execution > 1s, play "Thinking..." filler audio/sound.
- [ ] **Safety**: Sensitive tools must require verbal confirmation ("Are you sure?").
- [ ] **Observability**: Trace tool execution duration and arguments via OpenTelemetry/LogBus.

## Non-Functional Requirementse

### Documentation

- [ ] CHANGELOG.md updated
- [ ] README.md updated to describe how to configure and use tools with the VoiceOrchestrator. Example configurations and tool definitions should be provided. The format for the system prompt via `agent config` is documented clearly.
- [ ] API Documentation updated in `docs/openapi.yaml` if any API endpoints are added/modified.

### Observability

- [ ] Logs are structured and free of PII.
- [ ] Metrics added for tool execution duration, frequency of tool usage, and any errors encountered during tool execution.
- [ ] The arguments passed to each tool are logged (with appropriate redaction of sensitive information).
- [ ] The system prompt is included in the logs for debugging purposes.
- [ ] Alerting thresholds defined for tool latency and error rates.

### Testing

- [ ] Unit tests passed
- [ ] Integration tests passed
