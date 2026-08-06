"""Tool Framework — Phase 4 / Module.

A small registry of callable tools agents & the planning engine can use:
  - web_search : DuckDuckGo research (via llm.gateway)
  - browse     : fetch & extract a web page's text (Phase 8)
  - calculator : safe arithmetic evaluation
  - memory     : semantic recall (handled inside the agent core / RAG)
"""
import ast
import asyncio
import operator as op

from tools import browser
from llm import gateway

_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
    ast.USub: op.neg, ast.UAdd: op.pos,
}


def _eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("only numbers are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    try:
        tree = ast.parse((expression or "").strip(), mode="eval")
        result = _eval(tree.body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"{expression.strip()} = {result}"
    except Exception as e:
        return f"Calculator error: {e}"


TOOL_SPECS = [
    {"name": "web_search", "label": "Web Search",
     "description": "Search the web for up-to-date information.",
     "params": {"query": "string"}},
    {"name": "browse", "label": "Browse / Fetch URL",
     "description": "Open a web page and extract its readable text content.",
     "params": {"url": "string"}},
    {"name": "calculator", "label": "Calculator",
     "description": "Evaluate a math expression safely (+ - * / ** % //).",
     "params": {"expression": "string"}},
    {"name": "memory", "label": "Memory (RAG)",
     "description": "Recall the agent's uploaded knowledge and past conversations.",
     "params": {}},
]

TOOL_NAMES = [t["name"] for t in TOOL_SPECS]


def run_tool_sync(name: str, arg: str) -> dict:
    if name == "web_search":
        return {"tool": "web_search", "results": gateway.web_search(arg, 5)}
    if name == "browse":
        return {"tool": "browse", **browser.browse(arg)}
    if name == "calculator":
        return {"tool": "calculator", "result": calculator(arg)}
    return {"tool": name, "error": "unknown tool"}


async def run_tool(name: str, arg: str) -> dict:
    return await asyncio.to_thread(run_tool_sync, name, arg)
