"""Shared LLM helper: one place to build a provider + make a tracked chat call."""
import os
import re
from typing import Optional

from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


def get_provider(model: str, api_key: Optional[str] = None):
    """Return an OpenAIProvider, or None if no usable key (→ offline fallback)."""
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key or re.search(r"x{4,}", api_key):
        return None
    try:
        from src.core.openai_provider import OpenAIProvider
        return OpenAIProvider(model_name=model, api_key=api_key)
    except Exception:
        return None


def chat(provider, prompt: str, system: str, model: str,
         event: str = "LLM_CALL") -> Optional[str]:
    """Make a chat call with telemetry. Returns None on no-provider/error."""
    if provider is None:
        return None
    try:
        res = provider.generate(prompt, system_prompt=system)
        tracker.track_request(res.get("provider", "openai"), model,
                              res.get("usage", {}), res.get("latency_ms", 0))
        return (res.get("content", "") or "").strip()
    except Exception as e:  # noqa: BLE001
        logger.log_event(event + "_ERROR", {"error": str(e)})
        return None
