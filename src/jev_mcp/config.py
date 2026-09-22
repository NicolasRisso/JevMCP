"""Settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_url: str = "https://api.typesafe.ai/v1/systemone"
    model: str = "jev-latest"
    concurrency: int = 16
    # Jev allows 32k tokens for state + longest question. ~4 chars/token keeps a chunk near 15k tokens.
    chunk_chars: int = 60_000
    # Guard against a stray "**/*" sending an entire disk to the API.
    max_items: int = 500

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            api_key=os.environ.get("TYPESAFE_API_KEY", ""),
            api_url=os.environ.get("JEV_API_URL", cls.api_url),
            model=os.environ.get("JEV_MODEL", cls.model),
            concurrency=_int_env("JEV_CONCURRENCY", cls.concurrency),
            chunk_chars=_int_env("JEV_CHUNK_CHARS", cls.chunk_chars),
            max_items=_int_env("JEV_MAX_ITEMS", cls.max_items),
        )
