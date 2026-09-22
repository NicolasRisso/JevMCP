"""MCP server exposing Jev to coding agents."""

from __future__ import annotations

import asyncio
import json
import logging
import posixpath
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from jev_mcp import __version__
from jev_mcp.client import JevClient, JevError
from jev_mcp.compact import compact_response, is_unsure
from jev_mcp.config import ConfigError, Settings
from jev_mcp.sources import iter_items

VALID_TYPES = {"noul", "choice", "score"}

mcp = MCPServer("jev", version=__version__)
# The server logs at INFO, which makes httpx log every request line to stderr.
logging.getLogger("httpx").setLevel(logging.WARNING)


def validate_questions(questions: dict[str, Any]) -> None:
    if not questions:
        raise ValueError("questions must not be empty")
    for qid, q in questions.items():
        if q.get("type") not in VALID_TYPES:
            raise ValueError(f"{qid}: type must be one of {sorted(VALID_TYPES)}")
        if not q.get("instructions"):
            raise ValueError(f"{qid}: instructions are required")
        if q["type"] in ("choice", "score") and not q.get("criteria"):
            raise ValueError(f"{qid}: criteria are required for {q['type']}")


async def run_batch(
    client: JevClient,
    items: list[tuple[str, str]],
    questions: dict[str, Any],
    threshold: float,
    verbose: bool,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    unsure: list[str] = []
    tokens = 0

    async def one(item_id: str, state: str) -> None:
        nonlocal tokens
        try:
            resp = await client.ask(state, questions)
        except JevError as e:
            results[item_id] = {"error": str(e)}
            return
        tokens += resp.get("usage", {}).get("input_tokens", 0)
        results[item_id] = resp["answers"] if verbose else compact_response(resp, threshold)
        if any(is_unsure(a, threshold) for a in resp["answers"].values()):
            unsure.append(item_id)

    await asyncio.gather(*(one(i, s) for i, s in items))

    errors = {r["error"] for r in results.values() if "error" in r}
    if len(errors) == 1 and all("error" in r for r in results.values()):
        # e.g. a bad key: report once instead of once per item.
        raise ToolError(errors.pop())

    ordered = {k: results[k] for k, _ in items}
    if verbose:
        return {"results": ordered, "unsure": sorted(unsure), "input_tokens": tokens}
    return shrink(ordered, sorted(unsure), single_question=len(questions) == 1)


def shrink(results: dict[str, Any], unsure: list[str], single_question: bool) -> dict[str, Any]:
    """Cut repeated bytes: shared path prefix goes to `root`, one-question answers are unwrapped."""
    root = common_root(list(results))
    cut = len(root)
    out: dict[str, Any] = {}
    if root:
        out["root"] = root
    out["results"] = {
        k[cut:]: (next(iter(v.values())) if single_question and "error" not in v else v) for k, v in results.items()
    }
    if unsure:
        out["unsure"] = [u[cut:] for u in unsure]
    return out


def common_root(ids: list[str]) -> str:
    """Longest shared directory prefix (with trailing /) of path-like ids, else ''. Ids use forward slashes."""
    if len(ids) < 2:
        return ""
    try:
        root = posixpath.commonpath([posixpath.dirname(i.split("#")[0]) for i in ids])
    except ValueError:  # mixed drives or absolute/relative
        return ""
    if not root:
        return ""
    prefix = root.rstrip("/") + "/"
    return prefix if all(i.startswith(prefix) for i in ids) else ""


# Hand-written so the definition every agent loads stays small (no titles, no anyOf-null noise).
JEV_ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {"type": "object", "description": "{id:{type:noul|choice|score,instructions,criteria}}"},
        "paths": {"type": "array", "items": {"type": "string"}, "description": "files, globs or dirs"},
        "texts": {"type": "object", "additionalProperties": {"type": "string"}, "description": "{id:text}"},
        "threshold": {"type": "number", "default": 0.6},
        "verbose": {"type": "boolean", "default": False},
    },
    "required": ["questions"],
}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True), structured_output=False)
async def jev_ask(
    questions: dict[str, Any],
    paths: list[str] | None = None,
    texts: dict[str, str] | None = None,
    threshold: float = 0.6,
    verbose: bool = False,
) -> str:
    """Answer typed questions about files via the Jev classifier without reading them into your context.
noul=yes/no (criteria optional); choice: criteria {option:desc}; score: criteria [2-10 levels, low->high].
Batch all questions per call. Out: {root?,results:{item:answer or {qid:answer}},unsure?}.
noul -> P(yes) | [p,"?"]; choice/score -> [value,conf(,top2 probs)]. Open unsure items yourself.
Weak at counting, math, dates, multi-step reasoning."""
    try:
        validate_questions(questions)
        settings = Settings.from_env()
    except (ValueError, ConfigError) as e:
        # ToolError reaches the agent with its message; other exceptions become a generic error.
        raise ToolError(str(e)) from e
    items = list(iter_items(paths, texts, settings.chunk_chars))
    if not items:
        raise ToolError("no readable text found in paths/texts")
    if len(items) > settings.max_items:
        raise ToolError(f"{len(items)} items exceeds JEV_MAX_ITEMS={settings.max_items}; narrow the glob")
    async with JevClient(settings) as client:
        out = await run_batch(client, items, questions, threshold, verbose)
    return json.dumps(out, separators=(",", ":"), ensure_ascii=False)


mcp._tool_manager.get_tool("jev_ask").parameters = JEV_ASK_SCHEMA
