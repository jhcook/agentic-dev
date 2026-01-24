# ADR-011: Conversational Agent Framework Selection (LangGraph)

## Status

Proposed

## Context

The voice orchestrator implemented in INFRA-028 currently uses a placeholder agent that simply echoes user input. To provide real conversational AI capabilities, we need to select and integrate a robust agent framework that can:

1. Manage stateful, multi-turn conversations
2. Support tool calling and external integrations
3. Handle complex reasoning workflows
4. Provide streaming responses for low-latency voice interactions
5. Support error recovery and graceful degradation
6. Enable conversation checkpointing and resumption (critical for mobile apps)

The agent framework choice is a significant architectural decision that affects:

- Development velocity and maintainability
- Conversation quality and capabilities
- Scalability and production readiness
- Integration patterns with existing voice stack (STT/TTS)

## Decision

We will use **LangGraph** as the conversational agent framework for the voice orchestrator.

## Alternatives Considered

### 1. Custom ReAct Loop Implementation

**Pros**:

- Complete control over implementation
- No additional dependencies
- Tailored exactly to our needs

**Cons**:

- Significant engineering effort to build production-grade features
- Manual state management and checkpointing
- No streaming support out-of-box
- Difficult to implement multi-agent patterns
- Reinventing solved problems

### 2. LangChain Standard Chains

**Pros**:

- Well-documented and widely adopted
- Good integration with LLM providers
- Large community support

**Cons**:

- Limited state management capabilities
- Chains are stateless by default
- Complex to implement conversation history
- No built-in checkpointing
- Less flexible for complex workflows

### 3. LlamaIndex Agents

**Pros**:

- Strong focus on RAG (Retrieval-Augmented Generation)
- Good for knowledge base integration
- Simple API for basic agents

**Cons**:

- Less mature agent orchestration compared to LangGraph
- Limited graph-based workflow capabilities
- Fewer examples for voice/real-time use cases

### 4. CrewAI

**Pros**:

- Designed for multi-agent collaboration
- High-level abstractions

**Cons**:

- Opinionated framework, less flexibility
- Heavier weight for single-agent use case
- Less fine-grained control

## Rationale for LangGraph

### Production-Grade Features

1. **Stateful Graph-Based Orchestration**
   - Complex workflows with branching, loops, and conditional logic
   - Multi-step reasoning chains
   - Persistent state across conversation turns

2. **Native Streaming Support**

   ```python
   async for chunk in agent.astream(input):
       audio_chunk = await tts.speak(chunk)
       await websocket.send_bytes(audio_chunk)
   ```

   - Critical for low-latency voice responses
   - Better user experience (no waiting for full response)

3. **Checkpointing & Resumption**
   - Save conversation state at any point
   - Resume after interruptions (crucial for mobile apps)
   - Time-travel debugging for development

4. **Memory Management**
   - Built-in conversation history
   - Automatic context window management
   - Semantic memory (remember key facts across sessions)

### Advanced Capabilities

1. **Human-in-the-Loop**
   - Pause for user confirmation
   - Escalate complex decisions
   - Perfect for voice interactions

2. **Multi-Agent Systems** (future)**
   - Specialist agents (research, coding, analysis)
   - Coordinator patterns
   - Collaborative problem-solving

3. **Tool Orchestration**
   - Complex multi-step workflows
   - Automatic retry with different strategies
   - Graceful error handling

### Integration with Voice Stack

LangGraph integrates cleanly with our existing architecture:

- Works with `VoiceOrchestrator` pattern
- Compatible with FastAPI WebSocket endpoint
- Async/await native (matches our STT/TTS providers)
- Can be easily mocked for testing

## Consequences

### Positive

- **Reduced Development Time**: Avoid building state management, checkpointing, streaming from scratch
- **Production Ready**: Battle-tested framework with proven patterns
- **Scalability**: Designed for production workloads
- **Community Support**: Active development, extensive documentation, growing ecosystem
- **Future-Proof**: Enables advanced features (multi-agent, RAG) without major refactoring
- **Better UX**: Streaming responses, interrupt handling, conversation memory
- **Debugging**: Time-travel debugging and state inspection

### Negative

- **Additional Dependency**: Adds `langgraph` and `langchain` to dependencies (~10MB)
- **Learning Curve**: Team needs to learn LangGraph concepts (graphs, states, nodes, edges)
- **Abstraction Overhead**: Slight performance overhead vs custom implementation (negligible for I/O-bound voice)
- **Version Lock-in**: Need to stay current with LangGraph updates

### Neutral

- **Opinionated Patterns**: Framework guides architecture (generally positive, but less flexibility)
- **LangChain Ecosystem**: Inherits LangChain dependencies (good for integrations, adds weight)

## Implementation Notes

### Integration Points

1. **Replace Placeholder in `VoiceOrchestrator`**:

   ```python
   from langgraph.prebuilt import create_react_agent
   
   class VoiceOrchestrator:
       def __init__(self, session_id: str):
           self.session_id = session_id
           self.agent = create_react_agent(llm, tools)
           self.checkpointer = MemorySaver()
   ```

2. **Streaming Responses**:

   ```python
   async def process_audio(self, audio_chunk: bytes) -> bytes:
       text_input = await self.stt.listen(audio_chunk)
       
       async for chunk in self.agent.astream(
           {"messages": [("user", text_input)]},
           config={"configurable": {"thread_id": self.session_id}}
       ):
           if "agent" in chunk:
               response_text = chunk["agent"]["messages"][0].content
               return await self.tts.speak(response_text)
   ```

3. **Checkpointing for Mobile**:
   - Save state when WebSocket disconnects
   - Resume when reconnecting with same `session_id`

### Dependencies

```toml
[project.dependencies]
langgraph = ">=0.2.0"
langchain = ">=0.3.0"
langchain-openai = ">=0.2.0"  # or other LLM provider
```

### Testing Strategy

- Mock LangGraph agent for unit tests
- Integration tests with real agent (small model)
- Verify checkpointing and resumption
- Test streaming response handling

## Related

- **ADR-007**: Voice Service Abstraction Layer (STT/TTS interfaces)
- **ADR-008**: Unified Cloud Voice Provider (Deepgram)
- **INFRA-028**: Voice Logic Orchestration (WebSocket endpoint)
- **INFRA-034**: ReAct Agent Loop Engine (for CLI agent, different use case)

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)
- [Building Voice Assistants with LangGraph](https://blog.langchain.dev/langgraph-voice-agents/)
