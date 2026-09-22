"""Command line: `jev-mcp` serves over stdio; `install`, `uninstall` and `check` help with setup."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import time

import httpx

from jev_mcp.client import JevClient, JevError
from jev_mcp.config import PROVIDERS, ConfigError, Settings

CHECK_QUESTIONS = {"ok": {"type": "noul", "instructions": "Does the text say the system is working?"}}


def install_command(name: str, scope: str, provider: str | None, fallback: bool) -> list[str]:
    """`claude mcp add` invocation. API keys are NOT included: the server reads them from the environment."""
    cmd = ["claude", "mcp", "add", name, "--scope", scope]
    if provider:
        cmd += ["-e", f"JEV_PROVIDER={provider}"]
    if fallback:
        cmd += ["-e", "JEV_FALLBACK=true"]
    # The absolute interpreter path keeps working from any repo without jev-mcp on PATH.
    return cmd + ["--", sys.executable, "-m", "jev_mcp"]


def run_claude(cmd: list[str]) -> int:
    exe = shutil.which("claude")
    if not exe:
        print("`claude` CLI not found on PATH. Run this yourself:\n  " + subprocess.list2cmdline(cmd), file=sys.stderr)
        return 1
    return subprocess.call([exe, *cmd[1:]])


async def check(transport: httpx.AsyncBaseTransport | None = None) -> int:
    """Send one tiny question to every configured endpoint and report latency. Never prints keys."""
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        print(f"config: {e}", file=sys.stderr)
        return 1
    failed = 0
    for ep in settings.endpoints:
        single = Settings(endpoints=(ep,), concurrency=1)
        start = time.perf_counter()
        try:
            async with JevClient(single, transport=transport) as client:
                resp = await client.ask("Status: the system is working.", CHECK_QUESTIONS)
            ms = (time.perf_counter() - start) * 1000
            print(f"ok    {ep.provider:<10} {ep.model:<20} {ms:6.0f} ms  P(yes)={resp['answers']['ok']['noul']:.2f}")
        except JevError as e:
            failed += 1
            print(f"FAIL  {ep.provider:<10} {ep.model:<20} {e}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="jev-mcp", description="Jev MCP server. No subcommand: serve over stdio.")
    sub = parser.add_subparsers(dest="cmd")

    ins = sub.add_parser("install", help="register this server with Claude Code for the current directory")
    ins.add_argument("--scope", choices=["local", "user"], default="local",
                     help="local: this repo only, private (default). user: every repo")
    ins.add_argument("--name", default="jev")
    ins.add_argument("--provider", choices=sorted(PROVIDERS), help="pin JEV_PROVIDER for this registration")
    ins.add_argument("--fallback", action="store_true", help="set JEV_FALLBACK=true")

    rm = sub.add_parser("uninstall", help="remove the registration")
    rm.add_argument("--scope", choices=["local", "user"], default="local")
    rm.add_argument("--name", default="jev")

    sub.add_parser("check", help="verify API keys and connectivity with one tiny request per provider")

    args = parser.parse_args(argv)
    if args.cmd == "install":
        sys.exit(run_claude(install_command(args.name, args.scope, args.provider, args.fallback)))
    if args.cmd == "uninstall":
        sys.exit(run_claude(["claude", "mcp", "remove", args.name, "--scope", args.scope]))
    if args.cmd == "check":
        sys.exit(asyncio.run(check()))

    from jev_mcp.server import mcp

    mcp.run()
