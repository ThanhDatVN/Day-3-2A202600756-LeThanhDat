"""
A safe arithmetic calculator tool.

Why a dedicated tool? LLMs are unreliable at multi-step arithmetic. Offloading
the math to a deterministic tool is the whole point of the ReAct pattern:
the LLM *reasons* about which numbers to combine, the tool *computes*.

Security note (Production Readiness): we do NOT use eval(). We walk a parsed
AST and only allow numeric literals and the four basic operators, so a
malicious "expression" cannot execute arbitrary code.
"""
import ast
import operator

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_ALLOWED_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):  # number literal
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("only numeric literals are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression (+, -, *, /, **, %)."""
    try:
        tree = ast.parse(str(expression), mode="eval")
        result = _eval_node(tree.body)
        return f"The result of '{expression}' is {round(result, 4)}."
    except ZeroDivisionError:
        return "ERROR: division by zero."
    except Exception as e:  # noqa: BLE001 - surface any parse/eval issue to the agent
        return f"ERROR: could not evaluate '{expression}' ({e})."


CALCULATOR_TOOL = {
    "name": "calculator",
    "description": (
        "Evaluate an arithmetic expression. "
        "Args: expression (string, e.g. '2 * 1000 * 0.8 + 6'). "
        "Supports + - * / ** %. Use this for ALL math instead of computing yourself."
    ),
    "func": calculator,
}
