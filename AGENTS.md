# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project

JevMCP is a Python MCP server that exposes TypeSafe's Jev model (fast typed yes/no, choice and score judgements) to coding agents. Its goal is to **save the calling agent's context and time**: Jev reads the files, and the agent receives compact answers.

## Layout

- `src/jev_mcp/`: package (`server.py` tools, `client.py` HTTP, `sources.py` file expansion and chunking, `compact.py` output shrinking, `config.py` env settings)
- `tests/`: pytest suite. Uses `httpx.MockTransport`, so no network or API key is needed.
- `docs/`: `architecture.md`, `tools.md` (tool reference), `limitations.md`

## Commands

```bash
pip install -e .[dev]
pytest
jev-mcp            # run the server over stdio (needs TYPESAFE_API_KEY)
```

## Commits

- Use [Conventional Commits](https://www.conventionalcommits.org): `<type>(<optional scope>): <summary>`, imperative, lower case, no trailing period, summary ≤ 72 chars.
  - `feat`: new user-facing capability · `fix`: bug fix · `perf`: faster or smaller output/context
  - `refactor`: no behavior change · `test`: tests only · `docs`: docs only
  - `build`: packaging/dependencies · `ci`: CI config · `chore`: tooling, hooks, housekeeping
  - Breaking change: `feat!:` plus a `BREAKING CHANGE:` footer.
  - Examples: `feat(provider): support OpenRouter keys`, `docs: document threshold`.
- **Prefer small commits over big ones.** One logical change per commit. Split unrelated edits (e.g. a feature and a docs typo) into separate commits. Every commit must pass `pytest` on its own.
- A pre-push hook runs the test suite and blocks the push if it fails. Enable it once per clone with `git config core.hooksPath .githooks`. Don't bypass it with `--no-verify`.

## Rules

- Keep tool output compact. Any new field in a tool response costs every agent that uses it tokens on every call. Justify it.
- Tools take references (paths, globs, ids), not large pasted content.
- Tool docstrings are loaded into agents' context. Keep them short and precise.
- Never call the real Jev API in tests. Use `httpx.MockTransport`.
- Never commit API keys or `.env`.
- When the Jev API changes, update `docs/architecture.md` ("Jev API facts") along with the code.
- Update `docs/tools.md` whenever a tool's parameters or output change.
- Style: type hints, `from __future__ import annotations`, small modules, comments only where the reason isn't obvious.

## Jev reference

- Docs index: https://docs.typesafe.ai/llms.txt
- API: https://docs.typesafe.ai/api.md
- Known weaknesses: https://docs.typesafe.ai/model-jaggedness/jev-1.13.md
