"""Provider factory: build an LLMProvider from environment configuration."""
import os
from typing import Optional

from src.core.llm_provider import LLMProvider


def create_provider(provider: Optional[str] = None) -> LLMProvider:
    """
    Instantiate a provider by name (falls back to DEFAULT_PROVIDER env, then 'mock').
    Supported: 'mock' | 'openai' | 'gemini' | 'local'.
    """
    provider = (provider or os.getenv("DEFAULT_PROVIDER", "mock")).strip().lower()

    if provider == "mock":
        from src.core.mock_provider import MockProvider
        return MockProvider()

    if provider == "openai":
        from src.core.openai_provider import OpenAIProvider
        return OpenAIProvider(
            model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    if provider == "gemini":
        from src.core.gemini_provider import GeminiProvider
        return GeminiProvider(
            model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            api_key=os.getenv("GEMINI_API_KEY"),
        )

    if provider == "local":
        from src.core.local_provider import LocalProvider
        return LocalProvider(
            model_path=os.getenv("LOCAL_MODEL_PATH",
                                 "./models/Phi-3-mini-4k-instruct-q4.gguf"),
        )

    raise ValueError(f"Unknown provider '{provider}'. "
                     f"Use one of: mock, openai, gemini, local.")
