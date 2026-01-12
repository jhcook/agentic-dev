
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from agent.core.config import config
from agent.core.tokens import token_manager

logger = logging.getLogger(__name__)

class SmartRouter:
    """
    Routes AI requests to the optimal model based on configuration,
    complexity (tier), context window checks, and cost.
    """
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or (config.agent_dir / "router.yaml")
        self.config = self._load_config()
        self.models = self.config.get("models", {})
        self.settings = self.config.get("settings", {})

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            logger.warning(f"Router config not found at {self.config_path}, using defaults.")
            return {"models": {}, "settings": {}}
            
        try:
            text = self.config_path.read_text()
            return yaml.safe_load(text) or {}
        except Exception as e:
            logger.error(f"Failed to load router config: {e}")
            return {"models": {}, "settings": {}}

    def route(self, prompt: str, tier: str = None) -> Optional[Dict[str, Any]]:
        """
        Selects the best model for the given prompt and requested tier.
        
        Args:
            prompt: The input text to be processed.
            tier: Optional tier override (light, standard, advanced). 
                  If None, uses default from settings.
        
        Returns:
            Dictionary containing model configuration or None if no match found.
        """
        requested_tier = tier or self.settings.get("default_tier", "standard")
        
        # 1. Estimate Token Count
        # We start with a generic provider assumption to get a rough count first
        # Ideally we'd iterate, but input length is static.
        input_tokens = token_manager.count_tokens(prompt, provider="openai") # standard estimator
        
        # 2. Filter Candidates
        candidates = []
        for model_key, model_def in self.models.items():
            # Check Tier suitability
            if not self._tier_matches(model_def.get("tier"), requested_tier):
                continue
                
            # Check Context Window
            # Leave buffer for output tokens (heuristic: 10% or fixed 2k?)
            # For strict routing, input must be < context_window
            if input_tokens > model_def.get("context_window", 4096):
                continue
                
            candidates.append((model_key, model_def))
            
        if not candidates:
            logger.warning(f"No suitable models found for tier {requested_tier} with {input_tokens} tokens.")
            return None
            
        # 3. Sort by Cost (Input cost primarily)
        # Cost is defined per 1k tokens.
        candidates.sort(key=lambda x: x[1].get("cost_per_1k_input", 999.0))
        
        best_model_key, best_model_def = candidates[0]
        
        logger.info(f"Routed to {best_model_key} (Tier: {best_model_def.get('tier')}, " 
                    f"Cost/1k: ${best_model_def.get('cost_per_1k_input')}) "
                    f"for {input_tokens} tokens.")
                    
        return {
            "key": best_model_key,
            **best_model_def
        }
        
    def _tier_matches(self, model_tier: str, requested_tier: str) -> bool:
        """
        Check if model tier acts as a substitute for requested tier.
        Hierarchy: advanced > standard > light.
        If requested 'standard', we accept 'standard' or 'advanced'.
        If requested 'light', we accept anything.
        If requested 'advanced', we only accept 'advanced'.
        """
        tiers = ["light", "standard", "advanced"]
        try:
            model_idx = tiers.index(model_tier)
            req_idx = tiers.index(requested_tier)
            return model_idx >= req_idx
        except ValueError:
            return False

router = SmartRouter()
