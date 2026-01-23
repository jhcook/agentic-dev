import logging
from agent.core.utils import scrub_sensitive_data

logger = logging.getLogger(__name__)

class SecureManager:
    """
    Central security manager for scrubbing sensitive data and 
    validating safety constraints.
    """
    def __init__(self):
        pass

    def scrub(self, text: str) -> str:
        """
        Scrub sensitive data (PII, Secrets) from text.
        """
        if not text:
            return ""
        
        scrubbed = scrub_sensitive_data(text)
        
        # Additional safety checks could go here (e.g., detecting prompt injection patterns)
        
        return scrubbed
