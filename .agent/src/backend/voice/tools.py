from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

@tool
def lookup_documentation(query: str) -> str:
    """
    Search the agentic development documentation and knowledge base.
    Use this when the user asks technical questions about the agent's architecture, 
    workflows, or rules.
    """
    logger.info(f"Tool Executing: lookup_documentation(query={query})")
    # Simulation of a vector DB lookup
    # In real impl, this would query a ChromaDB or FAISS store
    
    # Simple keyword matching for demo/MVP
    query_lower = query.lower()
    
    if "agent" in query_lower and "rule" in query_lower:
        return "Rules are located in .agent/rules/. They enforce no secrets, PII redaction, and strict types."
    
    if "workflow" in query_lower:
        return "Workflows are markdown files in .agent/workflows/ that map to CLI commands."
        
    if "voice" in query_lower:
        return "The voice architecture uses a WebSocket router, a VAD processor, and a LangGraph orchestrator."
        
    return f"No specific documentation found for '{query}', but general best practices apply."

@tool
def dangerous_operation(target: str) -> str:
    """
    A sensitive operation that requires explicit confirmation.
    Use this only when the user explicitly requests to 'destroy' or 'delete' something.
    """
    logger.warning(f"Tool Executing: dangerous_operation(target={target})")
    return f"Operation on {target} simulated. In reality, I would have stopped for confirmation."
