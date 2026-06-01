"""
Chatbot baseline.

This is the "control group" for the lab: a plain single-shot LLM call with NO
tools and NO ReAct loop. It answers in one turn from parametric knowledge only.
Comparing it against the ReAct agent on multi-step tasks is the core experiment
(SCORING.md: "Evaluation & Analysis").
"""
from typing import Optional

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker

CHATBOT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question directly and "
    "concisely in a single response. You have no tools and cannot look anything "
    "up; rely only on what you already know."
)


class Chatbot:
    def __init__(self, llm: LLMProvider, system_prompt: str = CHATBOT_SYSTEM_PROMPT):
        self.llm = llm
        self.system_prompt = system_prompt

    def run(self, user_input: str) -> str:
        logger.log_event("CHATBOT_START", {
            "input": user_input, "model": self.llm.model_name,
        })
        result = self.llm.generate(user_input, system_prompt=self.system_prompt)
        tracker.track_request(
            provider=result.get("provider", "unknown"),
            model=self.llm.model_name,
            usage=result.get("usage", {}),
            latency_ms=result.get("latency_ms", 0),
        )
        answer = result.get("content", "")
        logger.log_event("CHATBOT_END", {"answer": answer})
        return answer
