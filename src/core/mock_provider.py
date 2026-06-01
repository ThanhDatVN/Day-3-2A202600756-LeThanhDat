"""
MockProvider: a fully offline, deterministic LLM stand-in.

It lets you exercise the *entire* system (ReAct loop, tool execution, telemetry,
log files, evaluation) without any API key or downloaded model. It is NOT a real
LLM - it is a small scripted "brain" that:

  * In CHATBOT mode (no ReAct instructions in the system prompt) returns a single
    direct answer - deliberately WRONG on multi-step questions, to reproduce the
    baseline's weakness.

  * In AGENT mode it emits the next Thought/Action by counting how many
    Observations are already in the transcript (= the current step index), and
    branches on the prompt VERSION:
      - v1 (no "STRICT RULES"): reproduces a real failure - it hallucinates a
        non-existent `calc_tax` tool and loops until timeout.
      - v2 ("STRICT RULES" present): solves the same task correctly with the
        real tools.

This is what makes the failure-analysis and v1-vs-v2 ablation reproducible.
"""
import re
from typing import Dict, Any, Optional, Generator

from src.core.llm_provider import LLMProvider


class MockProvider(LLMProvider):
    def __init__(self, model_name: str = "mock-react-1", api_key: Optional[str] = None):
        super().__init__(model_name, api_key)

    # ---------------------------------------------------------------- public
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        system_prompt = system_prompt or ""
        is_agent = "Action:" in system_prompt and "Thought:" in system_prompt
        is_v2 = "STRICT RULES" in system_prompt
        step = prompt.count("Observation:")
        question = self._extract_question(prompt)

        if is_agent:
            content = self._agent_script(question, step, is_v2)
        else:
            content = self._chatbot_script(question)

        usage = self._estimate_usage(prompt, system_prompt, content)
        latency_ms = 160 + len(content) // 2  # synthetic but deterministic
        return {
            "content": content,
            "usage": usage,
            "latency_ms": latency_ms,
            "provider": "mock",
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt)["content"]

    # ------------------------------------------------------------- internals
    @staticmethod
    def _extract_question(prompt: str) -> str:
        m = re.search(r"Question:\s*(.+)", prompt)
        text = m.group(1) if m else prompt
        return text.splitlines()[0].strip().lower()

    @staticmethod
    def _estimate_usage(prompt: str, system_prompt: str, completion: str) -> Dict[str, int]:
        p = (len(prompt) + len(system_prompt)) // 4
        c = max(1, len(completion) // 4)
        return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}

    # ---- chatbot baseline (no tools): confidently wrong on multi-step ----
    def _chatbot_script(self, question: str) -> str:
        if "iphone" in question and ("winner" in question or "total" in question):
            # Wrong: forgets the discount AND the shipping. Classic chatbot guess.
            return ("The total price for 2 iPhones is about 2000 USD. "
                    "(Coupons and shipping are usually small, so ~2000 USD.)")
        if "tax" in question and "macbook" in question:
            # Wrong: hallucinates a price and miscomputes.
            return "A MacBook is about $1500, so 10% tax is roughly $150."
        if "stock" in question or "samsung" in question:
            return "Yes, the Samsung Galaxy should be available to order."
        if "price" in question and "ipad" in question:
            return "An iPad costs around 600 USD."
        return "I'm a simple chatbot; here is my best guess based on general knowledge."

    # ---- agent ReAct scripts ----
    def _agent_script(self, question: str, step: int, is_v2: bool) -> str:
        if "iphone" in question and ("winner" in question or "hanoi" in question):
            return self._pick(self._scenario_ecommerce(), step)
        if "tax" in question and "macbook" in question:
            scenario = self._scenario_tax_v2() if is_v2 else self._scenario_tax_v1()
            return self._pick(scenario, step)
        if "samsung" in question or ("stock" in question and "samsung" in question):
            return self._pick(self._scenario_oos(), step)
        if "price" in question and "ipad" in question:
            return self._pick(self._scenario_simple_price(), step)
        return ("Thought: I now know the final answer.\n"
                "Final Answer: I don't have a tool to answer that precisely.")

    @staticmethod
    def _pick(scenario, step):
        if step < len(scenario):
            return scenario[step]
        return ("Thought: I now know the final answer.\n"
                "Final Answer: Based on the observations gathered, the task is complete.")

    # --- canonical multi-step success (6 steps, fits max_steps=6) ---
    @staticmethod
    def _scenario_ecommerce():
        return [
            ("Thought: I need the unit price of an iPhone.\n"
             "Action: get_price\n"
             'Action Input: {"item_name": "iPhone"}'),
            ("Thought: Confirm there are at least 2 units in stock.\n"
             "Action: check_stock\n"
             'Action Input: {"item_name": "iPhone"}'),
            ("Thought: Look up the discount for coupon WINNER.\n"
             "Action: get_discount\n"
             'Action Input: {"coupon_code": "WINNER"}'),
            ("Thought: Two iPhones weigh ~1.0 kg; get shipping to Hanoi.\n"
             "Action: calc_shipping\n"
             'Action Input: {"weight": 1.0, "destination": "Hanoi"}'),
            ("Thought: Total = 2 units * 1000 * (1 - 0.20) discount + 7 shipping.\n"
             "Action: calculator\n"
             'Action Input: {"expression": "2 * 1000 * 0.8 + 7"}'),
            ("Thought: I now know the final answer.\n"
             "Final Answer: 2 iPhones with coupon WINNER (20% off) = 1600 USD, "
             "plus 7 USD shipping to Hanoi => 1607 USD total. In stock: 5 units."),
        ]

    # --- out-of-stock: agent reacts to a failure observation ---
    @staticmethod
    def _scenario_oos():
        return [
            ("Thought: Check whether the Samsung Galaxy is in stock.\n"
             "Action: check_stock\n"
             'Action Input: {"item_name": "Samsung"}'),
            ("Thought: It is out of stock, so the user cannot buy it.\n"
             "Final Answer: Sorry, the Samsung Galaxy S24 is currently out of stock "
             "(0 units), so it cannot be ordered right now."),
        ]

    # --- simple single-step price lookup ---
    @staticmethod
    def _scenario_simple_price():
        return [
            ("Thought: Look up the iPad price.\n"
             "Action: get_price\n"
             'Action Input: {"item_name": "iPad"}'),
            ("Thought: I now know the final answer.\n"
             "Final Answer: An iPad Air costs 600 USD per unit."),
        ]

    # --- FAILURE trace (v1): hallucinated tool + loop until timeout ---
    @staticmethod
    def _scenario_tax_v1():
        hallucinate = ("Thought: I'll compute the tax with the tax tool.\n"
                       "Action: calc_tax\n"
                       'Action Input: {"amount": 2000, "rate": 10}')
        # Returns the same bad call every step -> demonstrates an infinite loop
        # that the max_steps guardrail eventually cuts off (TIMEOUT).
        return [hallucinate] * 8

    # --- same task fixed in v2: real tools, correct answer ---
    @staticmethod
    def _scenario_tax_v2():
        return [
            ("Thought: First get the MacBook price (no dedicated tax tool exists).\n"
             "Action: get_price\n"
             'Action Input: {"item_name": "MacBook"}'),
            ("Thought: 10% tax of 2000 = 2000 * 0.10, use the calculator.\n"
             "Action: calculator\n"
             'Action Input: {"expression": "2000 * 0.10"}'),
            ("Thought: I now know the final answer.\n"
             "Final Answer: A MacBook Air costs 2000 USD, so 10% tax is 200 USD."),
        ]
