"""
Vòng lặp ReAct dùng OpenAI function calling.

Thought → Action (tool call) → Observation → ... tối đa MAX_STEPS bước cho mỗi
người. Kết thúc khi gọi propose_pair / flag_unmatched, hoặc hết bước (tự flag).
Mỗi vòng được ghi telemetry (token/latency) + log đầy đủ để admin review.
"""
import json
import time
from typing import Optional, Set

from openai import OpenAI

from matchmaker import config
from matchmaker.agent.state import AgentState
from matchmaker.agent.tools import TOOL_SCHEMAS, ToolExecutor
from matchmaker.agent.prompts import build_initial_messages
from matchmaker.pipeline.store import ProfileStore
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


class ReactAgent:
    def __init__(self, store: ProfileStore, model: Optional[str] = None,
                 api_key: Optional[str] = None, max_steps: Optional[int] = None):
        self.store = store
        self.model = model or config.CHAT_MODEL
        self.max_steps = max_steps or config.MAX_STEPS
        self.client = OpenAI(api_key=api_key or config.OPENAI_API_KEY)

    def run(self, person_id: str, exclude: Optional[Set[str]] = None) -> AgentState:
        state = AgentState(person_id=person_id)
        ex = ToolExecutor(self.store, person_id, exclude=exclude)
        messages = build_initial_messages(self.store.anon(person_id))
        logger.log_event("HARDCASE_START", {"person": person_id})

        while state.steps < self.max_steps and state.result is None:
            state.steps += 1
            t0 = time.time()
            resp = self.client.chat.completions.create(
                model=self.model, messages=messages,
                tools=TOOL_SCHEMAS, tool_choice="auto")
            latency = int((time.time() - t0) * 1000)
            msg = resp.choices[0].message
            u = resp.usage
            tracker.track_request("openai", self.model, {
                "prompt_tokens": u.prompt_tokens, "completion_tokens": u.completion_tokens,
                "total_tokens": u.total_tokens}, latency)
            thought = (msg.content or "").strip()

            if not msg.tool_calls:
                state.log(thought, observation="(không gọi tool)")
                logger.log_event("HARDCASE_THOUGHT", {"person": person_id,
                                 "step": state.steps, "thought": thought})
                messages.append({"role": "assistant", "content": thought})
                messages.append({"role": "user", "content":
                                 "Hãy tiếp tục bằng cách gọi một tool (hoặc flag_unmatched nếu bế tắc)."})
                continue

            messages.append({"role": "assistant", "content": thought,
                "tool_calls": [{"id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls]})

            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                obs = ex.execute(name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(obs, ensure_ascii=False)})
                state.log(thought, action=name, args=args, observation=obs)
                logger.log_event("HARDCASE_ACTION", {"person": person_id, "step": state.steps,
                                 "action": name, "args": args, "observation": obs})
                thought = ""  # gắn thought vào tool call đầu tiên thôi

            if ex.result is not None:
                state.result = ex.result
                state.relaxations = ex.relaxations

        if state.result is None:
            state.result = {"type": "flag", "profile_id": person_id,
                            "reason": f"Vượt quá MAX_STEPS={self.max_steps} chưa tìm được cặp",
                            "suggested_action": "admin xem xét thủ công",
                            "relaxations": ex.relaxations}
        logger.log_event("HARDCASE_END", {"person": person_id, "steps": state.steps,
                         "result_type": state.result["type"]})
        return state
