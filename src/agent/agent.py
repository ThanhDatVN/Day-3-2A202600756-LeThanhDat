import json
import re
import inspect
from typing import List, Dict, Any, Optional, Tuple

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


class ReActAgent:
    """
    A ReAct-style agent implementing the Thought -> Action -> Observation loop.

    The agent keeps a running transcript. On every step it asks the LLM for the
    next Thought + Action, parses the Action, runs the matching tool, and feeds
    the Observation back into the transcript. It stops on "Final Answer:" or when
    `max_steps` is exhausted (the timeout guardrail).

    `version` selects the system prompt:
      - "v1": minimal ReAct instructions (baseline).
      - "v2": adds a worked few-shot example + strict-format / anti-loop guardrails
              derived from failures observed in v1 logs.
    """

    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]],
                 max_steps: int = 6, version: str = "v1"):
        self.llm = llm
        self.tools = tools
        self.tool_map = {t["name"]: t for t in tools}
        self.max_steps = max_steps
        self.version = version
        self.history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ prompt
    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            f"- {t['name']}: {t['description']}" for t in self.tools
        )
        tool_names = ", ".join(self.tool_map.keys())

        base = f"""You are a precise reasoning agent that solves tasks step by step using tools.

You have access to ONLY these tools:
{tool_descriptions}

Follow this EXACT format, one block per turn:
Thought: explain what you need to do next.
Action: the tool name, exactly one of [{tool_names}]
Action Input: a single-line JSON object with the tool arguments, e.g. {{"item_name": "iPhone"}}

After each Action you will be given:
Observation: the tool result.

Repeat Thought/Action/Action Input as many times as needed. When you have enough
information to answer, output:
Thought: I now know the final answer.
Final Answer: the answer to the user, including the concrete numbers."""

        if self.version == "v1":
            return base

        # v2 hardening: the few-shot + rules below were added after reading v1
        # failure traces (hallucinated tools, missing Action Input, loops).
        guardrails = """

STRICT RULES (read carefully):
1. Output exactly ONE Action per turn, then STOP and wait for the Observation.
   Never write your own "Observation:" line.
2. "Action Input" MUST be raw JSON only - no markdown, no backticks, no prose.
3. Only call tools from the allowed list. Do NOT invent tool names or arguments.
4. Do all arithmetic with the `calculator` tool; never compute numbers yourself.
5. If an Observation is an ERROR, fix the arguments and try again; do not repeat
   the identical failing call.

EXAMPLE
Question: What is the price of 3 iPads?
Thought: I need the unit price of an iPad first.
Action: get_price
Action Input: {"item_name": "iPad"}
Observation: Unit price of 'iPad Air' is 600.0 USD.
Thought: Now multiply 600 by 3 using the calculator.
Action: calculator
Action Input: {"expression": "600 * 3"}
Observation: The result of '600 * 3' is 1800.
Thought: I now know the final answer.
Final Answer: 3 iPads cost 1800 USD."""
        return base + guardrails

    # --------------------------------------------------------------------- run
    def run(self, user_input: str) -> str:
        logger.log_event("AGENT_START", {
            "input": user_input,
            "model": self.llm.model_name,
            "version": self.version,
            "max_steps": self.max_steps,
        })

        transcript = f"Question: {user_input}\n"
        system_prompt = self.get_system_prompt()
        steps = 0
        final_answer: Optional[str] = None

        while steps < self.max_steps:
            steps += 1

            # 1. Ask the LLM for the next Thought + Action.
            result = self.llm.generate(transcript, system_prompt=system_prompt)
            content = self._truncate_at_observation(result.get("content", ""))

            # Telemetry: token usage + latency for this LLM call.
            tracker.track_request(
                provider=result.get("provider", "unknown"),
                model=self.llm.model_name,
                usage=result.get("usage", {}),
                latency_ms=result.get("latency_ms", 0),
            )
            logger.log_event("AGENT_STEP", {"step": steps, "raw": content})

            # 2. Did the model produce a Final Answer?
            final_answer = self._parse_final_answer(content)
            if final_answer is not None:
                logger.log_event("FINAL_ANSWER", {"step": steps, "answer": final_answer})
                break

            # 3. Parse the Action.
            action, action_input_raw = self._parse_action(content)
            if action is None:
                logger.log_event("PARSE_ERROR", {
                    "step": steps,
                    "reason": "no Action or Final Answer found",
                    "raw": content,
                })
                transcript += (content +
                               "\nObservation: FORMAT ERROR - respond with either "
                               "'Action:' + 'Action Input:' or 'Final Answer:'.\n")
                continue

            # 4. Parse the JSON arguments.
            args, parse_err = self._parse_args(action_input_raw)
            if parse_err is not None:
                logger.log_event("JSON_PARSE_ERROR", {
                    "step": steps,
                    "tool": action,
                    "raw_input": action_input_raw,
                    "error": parse_err,
                })
                observation = (f"ERROR: Action Input was not valid JSON ({parse_err}). "
                               f"Output ONLY a raw JSON object.")
            else:
                observation = self._execute_tool(action, args, step=steps)

            transcript += f"{content}\nObservation: {observation}\n"
            logger.log_event("OBSERVATION", {
                "step": steps, "tool": action, "observation": observation,
            })
            self.history.append({"step": steps, "action": action,
                                 "args": args, "observation": observation})

        # Termination quality: did we finish, or hit the step budget?
        success = final_answer is not None
        if not success:
            logger.log_event("TIMEOUT", {"steps": steps, "max_steps": self.max_steps})
            final_answer = ("I could not complete the task within the allowed "
                            f"{self.max_steps} steps.")

        logger.log_event("AGENT_END", {
            "steps": steps,
            "success": success,
            "version": self.version,
        })
        return final_answer

    # ----------------------------------------------------------- tool execution
    def _execute_tool(self, tool_name: str, args: Any, step: int = -1) -> str:
        tool = self.tool_map.get(tool_name)
        if tool is None:
            # The LLM hallucinated a tool that does not exist.
            logger.log_event("HALLUCINATION_ERROR", {
                "step": step,
                "tool": tool_name,
                "available": list(self.tool_map.keys()),
            })
            return (f"ERROR: tool '{tool_name}' does not exist. "
                    f"Available tools: {', '.join(self.tool_map.keys())}.")

        func = tool["func"]
        try:
            if isinstance(args, dict):
                return str(func(**args))
            # Single bare value -> map onto the function's first parameter.
            params = list(inspect.signature(func).parameters)
            if params:
                return str(func(**{params[0]: args}))
            return str(func())
        except TypeError as e:
            # Wrong / missing arguments -> hallucinated argument shape.
            logger.log_event("TOOL_ARG_ERROR", {
                "step": step, "tool": tool_name, "args": args, "error": str(e),
            })
            return f"ERROR: bad arguments for '{tool_name}': {e}"
        except Exception as e:  # noqa: BLE001
            logger.log_event("TOOL_RUNTIME_ERROR", {
                "step": step, "tool": tool_name, "error": str(e),
            })
            return f"ERROR: tool '{tool_name}' failed: {e}"

    # --------------------------------------------------------------- parsing
    @staticmethod
    def _truncate_at_observation(text: str) -> str:
        """Cut anything the model hallucinated after its own Action."""
        idx = text.find("Observation:")
        return text[:idx].rstrip() if idx != -1 else text.strip()

    @staticmethod
    def _parse_final_answer(text: str) -> Optional[str]:
        m = re.search(r"Final Answer:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    @staticmethod
    def _parse_action(text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Return (tool_name, raw_action_input).
        Supports:
          Action: tool_name
          Action Input: {json}
        and the combined form:
          Action: tool_name({json})
        """
        # Combined form: Action: name(...)
        combined = re.search(r"Action:\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$",
                             text, re.MULTILINE | re.DOTALL)
        if combined:
            return combined.group(1).strip(), combined.group(2).strip()

        name_m = re.search(r"Action:\s*([A-Za-z_]\w*)", text)
        if not name_m:
            return None, None
        input_m = re.search(r"Action Input:\s*(.+)", text, re.DOTALL)
        raw_input = input_m.group(1).strip() if input_m else ""
        return name_m.group(1).strip(), raw_input

    @staticmethod
    def _parse_args(raw: str) -> Tuple[Any, Optional[str]]:
        """Parse the Action Input into a dict (or bare value). Returns (value, error)."""
        if raw is None:
            return None, "empty Action Input"
        cleaned = raw.strip()
        # Strip markdown code fences / backticks that LLMs love to add.
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        cleaned = cleaned.strip("`").strip()
        if not cleaned:
            return {}, None
        # Isolate the first {...} block if there is trailing prose.
        brace = re.search(r"\{.*\}", cleaned, re.DOTALL)
        candidate = brace.group(0) if brace else cleaned
        try:
            return json.loads(candidate), None
        except json.JSONDecodeError as e:
            # Fallback: a bare quoted/unquoted scalar (single-arg tools).
            if not brace:
                return cleaned.strip('"').strip("'"), None
            return None, str(e)
