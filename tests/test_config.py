import pytest

from jev_mcp.config import ConfigError, Settings

KEYS = ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "JEV_PROVIDER", "JEV_MODEL", "JEV_API_URL", "JEV_FALLBACK")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def providers():
    return [e.provider for e in Settings.from_env().endpoints]


def test_typesafe_key_selects_typesafe(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    (ep,) = Settings.from_env().endpoints
    assert (ep.provider, ep.api_key, ep.model) == ("typesafe", "ts", "jev-latest")
    assert ep.url.endswith("/v1/systemone")


def test_openrouter_key_selects_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    (ep,) = Settings.from_env().endpoints
    assert (ep.provider, ep.api_key, ep.model) == ("openrouter", "or", "typesafe/jev-1.13")
    assert ep.url == "https://openrouter.ai/api/alpha/decisions"


def test_typesafe_wins_when_both_set_and_no_fallback_by_default(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    assert providers() == ["typesafe"]


def test_explicit_provider_overrides(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("JEV_PROVIDER", "openrouter")
    assert providers() == ["openrouter"]


@pytest.mark.parametrize("primary,expected", [("typesafe", ["typesafe", "openrouter"]), ("openrouter", ["openrouter", "typesafe"])])
def test_fallback_adds_other_provider_after_primary(monkeypatch, primary, expected):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("JEV_PROVIDER", primary)
    monkeypatch.setenv("JEV_FALLBACK", "true")
    assert providers() == expected


def test_fallback_without_other_key_is_ignored(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("JEV_FALLBACK", "1")
    assert providers() == ["typesafe"]


def test_model_override_applies_to_primary_only(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("JEV_FALLBACK", "on")
    monkeypatch.setenv("JEV_MODEL", "jev-1.13.0")
    primary, fallback = Settings.from_env().endpoints
    assert (primary.model, fallback.model) == ("jev-1.13.0", "typesafe/jev-1.13")


def test_no_key_errors():
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_explicit_provider_without_key_errors(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("JEV_PROVIDER", "openrouter")
    with pytest.raises(ConfigError):
        Settings.from_env()
