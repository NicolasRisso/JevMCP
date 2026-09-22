"""MCP server exposing Jev to coding agents."""

from __future__ import annotations

import asyncio
import json
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
    return {
        "results": {k: results[k] for k, _ in items},
        "unsure": sorted(unsure),
        "items": len(items),
        "input_tokens": tokens,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def jev_ask(
    questions: dict[str, Any],
    paths: list[str] | None = None,
    texts: dict[str, str] | None = None,
    threshold: float = 0.6,
    verbose: bool = False,
) -> str:
    """Ask Jev (fast typed classifier) questions about files WITHOUT reading them into your context.

    questions: {id: {"type": "noul"|"choice"|"score", "instructions": str, "criteria": ...}}
      noul: yes/no, criteria optional. choice: criteria {option: description} (<=255).
      score: criteria = 2-10 level descriptions, low to high.
      All questions are answered in parallel per item, so batch them.
    paths: files, globs ("src/**/*.py") or directories. Large files are chunked as path#N.
    texts: {id: text} for small inline content.
    Returns {results: {item: {qid: answer}}, unsure: [items], items, input_tokens}.
      noul -> P(yes) or [p, "?"]; choice/score -> [value, confidence] (+ top-2 probs if unsure).
    Jev is weak at counting, math, dates and multi-step reasoning; verify "unsure" items yourself.
    """
    try:
        validate_questions(questions)
        settings = Settings.from_env()
    except (ValueError, ConfigError) as e:
        # ToolError reaches the agent with its message; other exceptions become a generic error.
        raise ToolError(str(e)) from e
    items = list(iter_items(paths, texts, settings.chunk_chars))
    if not items:
        return json.dumps({"error": "no readable text found in paths/texts"})
    if len(items) > settings.max_items:
        return json.dumps({"error": f"{len(items)} items exceeds JEV_MAX_ITEMS={settings.max_items}; narrow the glob"})
    async with JevClient(settings) as client:
        out = await run_batch(client, items, questions, threshold, verbose)
    return json.dumps(out, separators=(",", ":"), ensure_ascii=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
