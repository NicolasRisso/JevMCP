import asyncio
import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from jev_mcp.client import JevClient
from jev_mcp.config import Settings
from jev_mcp.server import run_batch, validate_questions


def fake_transport(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body["state"] == "boom":
            return httpx.Response(422, text="bad question")
        yes = "refund" in body["state"]
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {"wants_refund": {"type": "noul", "noul": 0.97 if yes else 0.52}},
                "usage": {"input_tokens": 10, "output_tokens": 1},
            },
        )

    return httpx.MockTransport(handler)


def test_run_batch_compacts_and_flags_unsure():
    calls = []
    questions = {"wants_refund": {"type": "noul", "instructions": "Does the user want a refund?"}}
    items = [("a", "I want a refund"), ("b", "hello"), ("c", "boom")]

    async def go():
        async with JevClient(Settings(api_key="k"), transport=fake_transport(calls)) as client:
            return await run_batch(client, items, questions, 0.6, verbose=False)

    out = asyncio.run(go())
    assert out["results"]["a"] == {"wants_refund": 0.97}
    assert out["results"]["b"] == {"wants_refund": [0.52, "?"]}
    assert "error" in out["results"]["c"]
    assert out["unsure"] == ["b"]
    assert out["input_tokens"] == 20
    assert calls[0]["model"] == "jev-latest"


def test_validate_questions_rejects_bad_type():
    with pytest.raises(ValueError):
        validate_questions({"q": {"type": "bool", "instructions": "x"}})


def test_validate_questions_requires_criteria_for_choice():
    with pytest.raises(ValueError):
        validate_questions({"q": {"type": "choice", "instructions": "x"}})


def test_tool_reports_readable_errors(monkeypatch):
    from jev_mcp.server import mcp

    for k in ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "JEV_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    q = {"q": {"type": "noul", "instructions": "x"}}

    # ToolError (unlike other exceptions) is shown to the agent with its message.
    with pytest.raises(ToolError, match="type must be one of"):
        asyncio.run(mcp.call_tool("jev_ask", {"questions": {"q": {"type": "bool"}}}))
    with pytest.raises(ToolError, match="OPENROUTER_API_KEY"):
        asyncio.run(mcp.call_tool("jev_ask", {"questions": q, "texts": {"a": "hi"}}))
