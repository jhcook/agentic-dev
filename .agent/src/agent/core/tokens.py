
import logging

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages token counting for various AI models.
    Uses tiktoken for OpenAI models and heuristics for others.
    """
    def __init__(self):
        self._encoding_cache = {}

    def count_tokens(self, text: str, provider: str = "openai", model_name: str = "gpt-4o") -> int:
        """
        Count tokens in a text string.
        
        Args:
            text: The text to count.
            provider: The AI provider (openai, gemini, gh).
            model_name: The specific model name (for tiktoken encoding selection).
            
        Returns:
            int: Estimated or exact token count.
        """
        if text is None:
            raise TypeError("Text cannot be None")
        if not isinstance(text, str):
            raise TypeError(f"Text must be a string, got {type(text)}")
            
        if not text:
            return 0
            
        if provider == "openai" or provider == "gh":
            return self._count_openai(text, model_name)
        elif provider == "gemini":
            # Gemini has a specific tokenizer but for now we use a slightly more conservative heuristic
            # or the 4 chars / token rule which is standard estimation.
            # Gemini documentation often says ~4 chars per token.
            return len(text) // 4
        else:
            # Fallback
            return len(text) // 4

    def _count_openai(self, text: str, model_name: str) -> int:
        try:
            # Map common names to encodings if needed, or rely on tiktoken's auto-detect
            # for 'gpt-4o', tiktoken usually knows it.
            encoding = self._get_encoding(model_name)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Failed to count tokens with tiktoken: {e}. using heuristic.")
            return len(text) // 4

    def _get_encoding(self, model_name: str):
        if model_name in self._encoding_cache:
            return self._encoding_cache[model_name]
            
        try:
            import tiktoken
            # Handle some known aliases or defaults
            if model_name.startswith("gpt-4"):
                encoding = tiktoken.encoding_for_model("gpt-4o") # default to 4o for modern 4-series
            elif model_name.startswith("gpt-3.5"):
                encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            else:
                encoding = tiktoken.get_encoding("cl100k_base") # standard for 4/3.5
                
            self._encoding_cache[model_name] = encoding
            return encoding
        except Exception:
            # Fallback to cl100k_base
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            self._encoding_cache[model_name] = encoding
            return encoding

token_manager = TokenManager()
