"""AgentState cho một lần xử lý một case khó."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentState:
    person_id: str
    steps: int = 0
    result: Optional[Dict[str, Any]] = None      # {"type": "proposal"|"flag", ...}
    trace: List[Dict[str, Any]] = field(default_factory=list)   # Thought/Action/Observation
    relaxations: List[Dict[str, Any]] = field(default_factory=list)

    def log(self, thought: str, action: Optional[str] = None,
            args: Optional[dict] = None, observation: Any = None):
        self.trace.append({"step": self.steps, "thought": thought,
                           "action": action, "args": args, "observation": observation})
