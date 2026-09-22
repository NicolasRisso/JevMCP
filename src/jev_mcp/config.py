"""Settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Both providers accept the same {model, state, questions} body and return the same answers.
PROVIDERS = {
    "typesafe": {
        "key_env": "TYPESAFE_API_KEY",
        "url": "https://api.typesafe.ai/v1/systemone",
        "model": "jev-latest",
    },
    "openrouter": {
        "key_env": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/alpha/decisions",
        "model": "typesafe/jev-1.13",
    },
}


class ConfigError(Exception):
    pass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _pick_provider() -> str:
    explicit = os.environ.get("JEV_PROVIDER", "").strip().lower()
    if explicit:
        if explicit not in PROVIDERS:
            raise ConfigError(f"JEV_PROVIDER must be one of {sorted(PROVIDERS)}, got {explicit!r}")
        return explicit
    for name, p in PROVIDERS.items():
        if os.environ.get(p["key_env"]):
            return name
    raise ConfigError("Set TYPESAFE_API_KEY (console.typesafe.ai/keys) or OPENROUTER_API_KEY (openrouter.ai/keys)")


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_url: str = PROVIDERS["typesafe"]["url"]
    model: str = PROVIDERS["typesafe"]["model"]
    provider: str = "typesafe"
    concurrency: int = 16
    # Jev allows 32k tokens for state + longest question. ~4 chars/token keeps a chunk near 15k tokens.
    chunk_chars: int = 60_000
    # Guard against a stray "**/*" sending an entire disk to the API.
    max_items: int = 500

    @classmethod
    def from_env(cls) -> Settings:
        provider = _pick_provider()
        p = PROVIDERS[provider]
        key = os.environ.get(p["key_env"], "")
        if not key:
            raise ConfigError(f"JEV_PROVIDER={provider} but {p['key_env']} is not set")
        return cls(
            api_key=key,
            api_url=os.environ.get("JEV_API_URL", p["url"]),
            model=os.environ.get("JEV_MODEL", p["model"]),
            provider=provider,
            concurrency=_int_env("JEV_CONCURRENCY", cls.concurrency),
            chunk_chars=_int_env("JEV_CHUNK_CHARS", cls.chunk_chars),
            max_items=_int_env("JEV_MAX_ITEMS", cls.max_items),
        )
