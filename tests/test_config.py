import pytest

from jev_mcp.config import ConfigError, Settings

KEYS = ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "JEV_PROVIDER", "JEV_MODEL", "JEV_API_URL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def test_typesafe_key_selects_typesafe(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    s = Settings.from_env()
    assert (s.provider, s.api_key, s.model) == ("typesafe", "ts", "jev-latest")
    assert s.api_url.endswith("/v1/systemone")


def test_openrouter_key_selects_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    s = Settings.from_env()
    assert (s.provider, s.api_key, s.model) == ("openrouter", "or", "typesafe/jev-1.13")
    assert s.api_url == "https://openrouter.ai/api/alpha/decisions"


def test_typesafe_wins_when_both_set(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    assert Settings.from_env().provider == "typesafe"


def test_explicit_provider_overrides(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("JEV_PROVIDER", "openrouter")
    assert Settings.from_env().api_key == "or"


def test_model_override(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("JEV_MODEL", "~typesafe/jev-latest")
    assert Settings.from_env().model == "~typesafe/jev-latest"


def test_no_key_errors():
    with pytest.raises(ConfigError):
        Settings.from_env()


def test_explicit_provider_without_key_errors(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("JEV_PROVIDER", "openrouter")
    with pytest.raises(ConfigError):
        Settings.from_env()
