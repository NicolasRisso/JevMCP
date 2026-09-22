"""Settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

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

TRUTHY = {"1", "true", "yes", "on"}


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Endpoint:
    provider: str
    api_key: str
    url: str
    model: str

    @classmethod
    def default(cls, provider: str, api_key: str) -> Endpoint:
        p = PROVIDERS[provider]
        return cls(provider, api_key, p["url"], p["model"])


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _key(provider: str) -> str:
    return os.environ.get(PROVIDERS[provider]["key_env"], "")


def _pick_provider() -> str:
    explicit = os.environ.get("JEV_PROVIDER", "").strip().lower()
    if explicit:
        if explicit not in PROVIDERS:
            raise ConfigError(f"JEV_PROVIDER must be one of {sorted(PROVIDERS)}, got {explicit!r}")
        return explicit
    for name in PROVIDERS:
        if _key(name):
            return name
    raise ConfigError("Set TYPESAFE_API_KEY (console.typesafe.ai/keys) or OPENROUTER_API_KEY (openrouter.ai/keys)")


def endpoints_from_env() -> tuple[Endpoint, ...]:
    """Primary endpoint first, then the other provider if JEV_FALLBACK is on and its key is set."""
    primary = _pick_provider()
    key = _key(primary)
    if not key:
        raise ConfigError(f"JEV_PROVIDER={primary} but {PROVIDERS[primary]['key_env']} is not set")
    p = PROVIDERS[primary]
    # JEV_MODEL / JEV_API_URL only override the primary: model names differ between providers.
    eps = [Endpoint(primary, key, os.environ.get("JEV_API_URL", p["url"]), os.environ.get("JEV_MODEL", p["model"]))]
    if os.environ.get("JEV_FALLBACK", "").strip().lower() in TRUTHY:
        eps += [Endpoint.default(name, _key(name)) for name in PROVIDERS if name != primary and _key(name)]
    return tuple(eps)


@dataclass(frozen=True)
class Settings:
    endpoints: tuple[Endpoint, ...] = field(default_factory=tuple)
    concurrency: int = 16
    # Jev allows 32k tokens for state + longest question. ~4 chars/token keeps a chunk near 15k tokens.
    chunk_chars: int = 60_000
    # Guard against a stray "**/*" sending an entire disk to the API.
    max_items: int = 500

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            endpoints=endpoints_from_env(),
            concurrency=_int_env("JEV_CONCURRENCY", cls.concurrency),
            chunk_chars=_int_env("JEV_CHUNK_CHARS", cls.chunk_chars),
            max_items=_int_env("JEV_MAX_ITEMS", cls.max_items),
        )
