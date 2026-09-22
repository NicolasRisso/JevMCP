import asyncio

import httpx
import pytest

from jev_mcp.client import JevClient, JevError
from jev_mcp.config import Endpoint, Settings

OK = {"answers": {"q": {"type": "noul", "noul": 0.9}}}
Q = {"q": {"type": "noul", "instructions": "q"}}
BOTH = Settings(endpoints=(Endpoint.default("typesafe", "ts"), Endpoint.default("openrouter", "or")))


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr("jev_mcp.client.asyncio.sleep", lambda s: real_sleep(0))


def transport(status_by_host, calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.host, request.headers["authorization"]))
        status = status_by_host[request.url.host]
        if status == "down":
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json=OK) if status == 200 else httpx.Response(status, text="nope")

    return httpx.MockTransport(handler)


def run(settings, statuses, n=1):
    calls = []

    async def go():
        async with JevClient(settings, transport=transport(statuses, calls)) as c:
            return await asyncio.gather(*(c.ask("s", Q) for _ in range(n)), return_exceptions=True)

    return asyncio.run(go()), calls


TS, OR = "api.typesafe.ai", "openrouter.ai"


def test_primary_success_never_touches_fallback():
    (res,), calls = run(BOTH, {TS: 200, OR: 200})
    assert res == OK
    assert calls == [(TS, "Bearer ts")]


@pytest.mark.parametrize("status", [401, 402, 500, 529, "down"])
def test_provider_failures_fall_back(status):
    (res,), calls = run(BOTH, {TS: status, OR: 200})
    assert res == OK
    assert calls[-1] == (OR, "Bearer or")


def test_rate_limit_retries_only_once_before_fallback():
    _, calls = run(BOTH, {TS: 429, OR: 200})
    assert [h for h, _ in calls] == [TS, TS, OR]


@pytest.mark.parametrize("status", [400, 422])
def test_bad_request_does_not_fall_back(status):
    (res,), calls = run(BOTH, {TS: status, OR: 200})
    assert isinstance(res, JevError) and str(status) in str(res)
    assert all(h == TS for h, _ in calls)


def test_dead_key_is_skipped_for_rest_of_batch():
    single = Settings(endpoints=BOTH.endpoints, concurrency=1)
    results, calls = run(single, {TS: 401, OR: 200}, n=3)
    assert results == [OK, OK, OK]
    assert [h for h, _ in calls].count(TS) == 1


def test_both_failing_reports_both_providers():
    (res,), _ = run(BOTH, {TS: 401, OR: 402})
    assert isinstance(res, JevError)
    assert "typesafe: HTTP 401" in str(res) and "openrouter: HTTP 402" in str(res)


def test_single_endpoint_dead_key_gives_identical_errors():
    single = Settings(endpoints=BOTH.endpoints[:1], concurrency=1)
    results, calls = run(single, {TS: 401}, n=3)
    assert len(calls) == 1
    assert len({str(r) for r in results}) == 1
