import asyncio
import sys

import httpx
import pytest

from jev_mcp.cli import check, install_command

KEYS = ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "JEV_PROVIDER", "JEV_FALLBACK", "JEV_MODEL", "JEV_API_URL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def test_install_command_defaults_to_local_scope_and_absolute_python():
    cmd = install_command("jev", "local", None, False)
    assert cmd == ["claude", "mcp", "add", "jev", "--scope", "local", "--", sys.executable, "-m", "jev_mcp"]


def test_install_command_pins_provider_and_fallback_but_never_keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    cmd = install_command("jev", "user", "openrouter", True)
    assert ["-e", "JEV_PROVIDER=openrouter"] == cmd[6:8]
    assert ["-e", "JEV_FALLBACK=true"] == cmd[8:10]
    assert not any("secret" in c or "API_KEY" in c for c in cmd)


def test_check_reports_each_endpoint(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("JEV_PROVIDER", "openrouter")
    monkeypatch.setenv("JEV_FALLBACK", "true")

    def handler(request):
        if request.url.host == "api.typesafe.ai":
            return httpx.Response(401, text="invalid key")
        return httpx.Response(200, json={"answers": {"ok": {"type": "noul", "noul": 0.98}}})

    code = asyncio.run(check(httpx.MockTransport(handler)))
    out = capsys.readouterr().out
    assert code == 1
    assert "ok    openrouter" in out and "P(yes)=0.98" in out
    assert "FAIL  typesafe" in out and "401" in out


def test_check_without_keys_fails_cleanly(capsys):
    assert asyncio.run(check()) == 1
    assert "OPENROUTER_API_KEY" in capsys.readouterr().err
