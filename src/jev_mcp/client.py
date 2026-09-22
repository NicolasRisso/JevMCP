"""Thin async client for Jev (TypeSafe System One or OpenRouter Decisions endpoint)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from jev_mcp.config import Endpoint, Settings

RETRY_STATUSES = {429, 502, 503, 529}
MAX_ATTEMPTS = 4
# With a fallback available, switching providers beats waiting out ~7s of backoff.
ATTEMPTS_BEFORE_FALLBACK = 2
# The request itself is wrong: the other provider would reject it too.
NO_FALLBACK_STATUSES = {400, 413, 422}
# Key/credit problems won't fix themselves within one batch: stop calling that provider.
DEAD_STATUSES = {401, 402, 403}


class JevError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class JevClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.endpoints:
            raise ValueError("settings.endpoints is empty")
        self._settings = settings
        self._sem = asyncio.Semaphore(settings.concurrency)
        self._http = httpx.AsyncClient(timeout=30, transport=transport)
        self._dead: dict[str, str] = {}  # provider -> error that disabled it

    async def __aenter__(self) -> JevClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._http.aclose()

    async def ask(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        """Send one state with all its questions, falling back to later endpoints on provider failures."""
        endpoints = self._settings.endpoints
        errors: list[str] = []
        async with self._sem:
            for i, ep in enumerate(endpoints):
                has_fallback = any(e.provider not in self._dead for e in endpoints[i + 1 :])
                attempts = ATTEMPTS_BEFORE_FALLBACK if has_fallback else MAX_ATTEMPTS
                if ep.provider in self._dead:
                    errors.append(self._dead[ep.provider])
                    continue
                try:
                    return await self._post(ep, state, questions, attempts)
                except JevError as e:
                    msg = f"{ep.provider}: {e}" if len(endpoints) > 1 else str(e)
                    if e.status in NO_FALLBACK_STATUSES:
                        raise JevError(msg, e.status) from e
                    if e.status in DEAD_STATUSES:
                        self._dead[ep.provider] = msg
                    errors.append(msg)
        raise JevError("; ".join(errors))

    async def _post(self, ep: Endpoint, state: Any, questions: dict[str, Any], attempts: int) -> dict[str, Any]:
        payload = {"model": ep.model, "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {ep.api_key}"}
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                r = await self._http.post(ep.url, json=payload, headers=headers)
            except httpx.TransportError as e:
                if not last:
                    await asyncio.sleep(2**attempt)
                    continue
                raise JevError(f"network error: {e!r}") from e
            if r.status_code in RETRY_STATUSES and not last:
                await asyncio.sleep(2**attempt)
                continue
            if r.is_error:
                raise JevError(f"HTTP {r.status_code}: {r.text[:300]}", r.status_code)
            return r.json()
        raise JevError("unreachable")
