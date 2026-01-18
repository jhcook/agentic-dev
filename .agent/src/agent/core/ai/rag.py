# .agent/src/agent/core/ai/rag.py

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ...config import is_ai_configured
from .llm_service import AIService, RateLimitError


class RAGService:
    def __init__(self, ai_service: AIService):
        if not is_ai_configured():
            raise ValueError("AI Service is not configured. Check your LLM_API_KEY in .env file.")
        self.ai_service = ai_service

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitError)
    )
    async def answer_query(self, query: str, context: str) -> str:
        if not context:
            return "I couldn't find any relevant information in the repository to answer your question. Please try rephrasing."

        system_prompt = """
        You are a helpful AI assistant for software developers.
        Answer the user's question based *only* on the provided context from the codebase.
        The context consists of multiple file snippets, each marked with `--- START filepath ---` and `--- END filepath ---`.
        When you use information from a file, you MUST cite it at the end of your answer like this: [Source: filepath].
        If the context does not contain the answer, state that you cannot answer the question with the given information. Do not make things up.
        """
        
        user_prompt = f"CONTEXT:\n{context}\n\nQUESTION:\n{query}"
        
        response = await self.ai_service.query(system_prompt, user_prompt)
        return response