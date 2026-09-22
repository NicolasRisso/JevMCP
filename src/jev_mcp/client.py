"""Thin async client for Jev (TypeSafe System One or OpenRouter Decisions endpoint)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from jev_mcp.config import Settings

RETRY_STATUSES = {429, 502, 503, 529}
MAX_ATTEMPTS = 4


class JevError(Exception):
    pass


class JevClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self._settings = settings
        self._sem = asyncio.Semaphore(settings.concurrency)
        self._http = httpx.AsyncClient(
            timeout=30,
            transport=transport,
            headers={"Authorization": f"Bearer {settings.api_key}"},
        )

    async def __aenter__(self) -> JevClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._http.aclose()

    async def ask(self, state: Any, questions: dict[str, Any]) -> dict[str, Any]:
        """Send one state with all its questions. Returns the raw API response."""
        payload = {"model": self._settings.model, "state": state, "questions": questions}
        async with self._sem:
            for attempt in range(MAX_ATTEMPTS):
                try:
                    r = await self._http.post(self._settings.api_url, json=payload)
                except httpx.TransportError as e:
                    if attempt < MAX_ATTEMPTS - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise JevError(f"network error: {e!r}") from e
                if r.status_code in RETRY_STATUSES and attempt < MAX_ATTEMPTS - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                if r.is_error:
                    raise JevError(f"HTTP {r.status_code}: {r.text[:300]}")
                return r.json()
        raise JevError("unreachable")
