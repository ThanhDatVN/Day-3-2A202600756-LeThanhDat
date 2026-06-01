import time
from typing import Dict, Any, List
from src.telemetry.logger import logger

class PerformanceTracker:
    """
    Tracking industry-standard metrics for LLMs.
    """
    def __init__(self):
        self.session_metrics = []

    def track_request(self, provider: str, model: str, usage: Dict[str, int], latency_ms: int):
        """
        Logs a single request metric to our telemetry.
        """
        metric = {
            "provider": provider,
            "model": model,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "latency_ms": latency_ms,
            "cost_estimate": self._calculate_cost(model, usage) # Mock cost calculation
        }
        self.session_metrics.append(metric)
        logger.log_event("LLM_METRIC", metric)

    # Public pricing, USD per 1K tokens, as (prompt, completion).
    # Local/mock models are free. Unknown models fall back to a flat estimate.
    PRICING = {
        "gpt-4o": (0.005, 0.015),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gemini-1.5-flash": (0.000075, 0.0003),
        "gemini-1.5-pro": (0.00125, 0.005),
    }

    def _calculate_cost(self, model: str, usage: Dict[str, int]) -> float:
        """Estimate request cost in USD from per-1K-token public pricing."""
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)

        # Free local / mock models.
        if model in ("mock-react-1",) or model.endswith(".gguf"):
            return 0.0

        in_rate, out_rate = self.PRICING.get(model, (0.001, 0.002))  # fallback
        cost = (prompt_t / 1000) * in_rate + (completion_t / 1000) * out_rate
        return round(cost, 6)

# Global tracker instance
tracker = PerformanceTracker()
