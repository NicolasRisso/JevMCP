import asyncio
import inspect
import json
import os

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from jev_mcp.client import JevClient
from jev_mcp.config import Endpoint, Settings

SETTINGS = Settings(endpoints=(Endpoint.default("typesafe", "k"),))
from jev_mcp.server import JEV_ASK_SCHEMA, common_root, jev_ask, run_batch, shrink, validate_questions


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
        async with JevClient(SETTINGS, transport=fake_transport(calls)) as client:
            return await run_batch(client, items, questions, 0.6, verbose=False)

    out = asyncio.run(go())
    # single question -> answers unwrapped; no token/item counters in compact mode
    assert out["results"]["a"] == 0.97
    assert out["results"]["b"] == [0.52, "?"]
    assert "error" in out["results"]["c"]
    assert out["unsure"] == ["b"]
    assert set(out) == {"results", "unsure"}
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


def ok_transport():
    return httpx.MockTransport(
        lambda r: httpx.Response(200, json={"answers": {"x": {"type": "noul", "noul": 0.99}, "y": {"type": "noul", "noul": 0.01}}})
    )


def test_multi_question_keeps_ids_and_omits_empty_unsure():
    async def go():
        async with JevClient(SETTINGS, transport=ok_transport()) as c:
            qs = {"x": {"type": "noul", "instructions": "x"}, "y": {"type": "noul", "instructions": "y"}}
            return await run_batch(c, [("a", "t")], qs, 0.6, verbose=False)

    assert asyncio.run(go()) == {"results": {"a": {"x": 0.99, "y": 0.01}}}


def test_identical_errors_collapse_into_one_tool_error():
    bad = httpx.MockTransport(lambda r: httpx.Response(401, text="invalid key"))

    async def go():
        async with JevClient(SETTINGS, transport=bad) as c:
            return await run_batch(c, [("a", "t"), ("b", "t")], {"q": {"type": "noul", "instructions": "q"}}, 0.6, False)

    with pytest.raises(ToolError, match="401"):
        asyncio.run(go())


def test_common_root_strips_shared_directory():
    sep = "/"
    ids = [f"reviews{sep}2026{sep}a.txt", f"reviews{sep}2026{sep}b.txt#1"]
    assert common_root(ids) == f"reviews{sep}2026{sep}"
    assert common_root(["a", "b"]) == ""
    assert common_root([f"x{sep}a.txt"]) == ""
    out = shrink({ids[0]: {"q": 1}, ids[1]: {"q": 0}}, [ids[1]], single_question=True)
    assert out == {"root": f"reviews{sep}2026{sep}", "results": {"a.txt": 1, "b.txt#1": 0}, "unsure": ["b.txt#1"]}


def test_advertised_schema_matches_signature_and_has_no_output_schema():
    from jev_mcp.server import mcp

    params = set(inspect.signature(jev_ask).parameters)
    assert set(JEV_ASK_SCHEMA["properties"]) == params
    (tool,) = asyncio.run(mcp.list_tools())
    assert tool.output_schema is None
    assert tool.input_schema == JEV_ASK_SCHEMA


def test_network_error_is_per_item_not_fatal(monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr("jev_mcp.client.asyncio.sleep", lambda s: real_sleep(0))

    def handler(request):
        if json.loads(request.content)["state"] == "down":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"answers": {"q": {"type": "noul", "noul": 0.9}}})

    async def go():
        async with JevClient(SETTINGS, transport=httpx.MockTransport(handler)) as c:
            return await run_batch(c, [("a", "up"), ("b", "down")], {"q": {"type": "noul", "instructions": "q"}}, 0.6, False)

    out = asyncio.run(go())
    assert out["results"]["a"] == 0.9
    assert "network error" in out["results"]["b"]["error"]
