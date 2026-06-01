"""Tool registry. Import get_all_tools() to feed the agent."""
from typing import Any, Dict, List

from src.tools.ecommerce_tools import ECOMMERCE_TOOLS
from src.tools.calculator_tool import CALCULATOR_TOOL


def get_all_tools() -> List[Dict[str, Any]]:
    """Return the full list of tool specs available to the agent."""
    return [*ECOMMERCE_TOOLS, CALCULATOR_TOOL]


def get_tool_map() -> Dict[str, Dict[str, Any]]:
    """Name -> tool spec, for quick lookup."""
    return {t["name"]: t for t in get_all_tools()}
