# JevMCP

**Give your AI coding agent a fast, cheap second brain for yes/no, multiple-choice and scoring questions.**

JevMCP is an open-source [MCP](https://modelcontextprotocol.io) server that lets agents such as Claude Code and Cursor hand those questions off to [TypeSafe's Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev). Jev reads the files, and the agent gets back a compact answer with a confidence score for each one. It works with a TypeSafe **or** an OpenRouter API key.

Why it helps: to answer "which of these 300 files mention X?", an agent normally reads all 300 files into its context. With JevMCP it gets back a short table of answers instead. That uses fewer tokens, runs faster, and costs very little (Jev charges $0.042 per million input tokens, and each request takes 70–500 ms).

> Status: early (0.1.0). The API shape may change.

## How it works

```
agent ──jev_ask(questions, paths)──▶ JevMCP ──reads files, chunks, fans out──▶ Jev API
agent ◀── {file: {q: [answer, confidence]}, unsure: [...]} ◀── compacts answers ◀──┘
```

- All questions for one file go in **one** request (Jev answers them in parallel).
- Requests to Jev for different files run concurrently.
- Confident answers come back as a few characters each. **Unsure** answers also include the top two probabilities and are listed in `unsure`, so the agent knows which files to open itself.

## Install

### 1. Get the package

From a clone (recommended while JevMCP is pre-release):

```bash
git clone https://github.com/NicolasRisso/JevMCP
```
```bash
cd JevMCP && python -m venv .venv && .venv/Scripts/pip install -e .
```

On macOS/Linux use `.venv/bin/pip`. It's an editable install, so a `git pull` takes effect in every repo using it the next time the server starts.

### 2. Provide an API key

You need **one** of these. Either one works:

- `OPENROUTER_API_KEY`: your OpenRouter key. Jev is served through OpenRouter's alpha Decisions endpoint.
- `TYPESAFE_API_KEY`: from https://console.typesafe.ai/keys

Set it as a user environment variable so every repo can use it without copying it around. On Windows, set it under *System Properties → Environment Variables*; on macOS/Linux, add `export OPENROUTER_API_KEY=...` to your shell profile. Then restart Claude Code.

### 3. Register it in a repo (one command)

From the root of the repo where you want to use it:

```bash
D:/path/to/JevMCP/.venv/Scripts/jev-mcp install
```

This runs `claude mcp add jev --scope local -- <that venv's python> -m jev_mcp`:
- **Local scope:** only this repo, and stored in your Claude Code user config, **not** in the repo. Nothing gets committed.
- `--scope user` registers it once for every repo.
- `--provider openrouter` and `--fallback` pin the provider settings described below.
- **Keys are never written by the installer.** The server reads them from your environment.
- `jev-mcp uninstall` removes the registration.

### 4. Verify

```bash
D:/path/to/JevMCP/.venv/Scripts/jev-mcp check
```

This sends one tiny request (a fraction of a cent) to each configured provider and prints the latency and the result. It never prints keys.

### Linux servers (over SSH)

On a headless box, skip the clone and install straight from GitHub with [pipx](https://pipx.pypa.io):

```bash
pipx install git+https://github.com/NicolasRisso/JevMCP.git
```
```bash
echo 'export OPENROUTER_API_KEY=sk-or-...' >> ~/.bashrc && source ~/.bashrc
```
```bash
jev-mcp install --scope user && jev-mcp check
```

The `claude` CLI must be installed on that server. Update later with `pipx upgrade jev-mcp`. For many servers, put these lines in a script and run `ssh host 'bash -s' < setup.sh`.

### Other MCP clients

Run `python -m jev_mcp` (or `jev-mcp`) over stdio with a key in the environment.

## Example

```json
{
  "paths": ["reviews/**/*.txt"],
  "questions": {
    "mentions_cleanliness": {"type": "noul", "instructions": "Does the review mention cleanliness?"},
    "sentiment": {"type": "choice", "instructions": "Overall sentiment of the review",
                  "criteria": {"positive": "Mostly positive", "negative": "Mostly negative", "mixed": "Both"}}
  }
}
```

Returns (the shared folder moves into `root`, and `unsure` lists what to check by hand):

```json
{"root":"reviews/","results":{"1.txt":{"mentions_cleanliness":0.96,"sentiment":["positive",0.94]},
 "2.txt":{"mentions_cleanliness":[0.51,"?"],"sentiment":["mixed",0.42,{"mixed":0.5,"negative":0.41}]}},
 "unsure":["2.txt"]}
```

The whole tool definition adds about 1 KB to the agent's context.

See [docs/tools.md](docs/tools.md) for the full tool reference.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `TYPESAFE_API_KEY` | | TypeSafe key. Set this or `OPENROUTER_API_KEY` |
| `OPENROUTER_API_KEY` | | OpenRouter key. Set this or `TYPESAFE_API_KEY` |
| `JEV_PROVIDER` | auto | Which key to use: `typesafe` or `openrouter`. Auto picks TypeSafe if its key is set, otherwise OpenRouter |
| `JEV_FALLBACK` | off | `true`: if the chosen provider fails, retry on the other one (needs both keys) |
| `JEV_MODEL` | `jev-latest` / `typesafe/jev-1.13` | Model for the **primary** provider (TypeSafe / OpenRouter default) |
| `JEV_API_URL` | provider's endpoint | Endpoint URL for the **primary** provider |
| `JEV_CONCURRENCY` | `16` | Max requests to Jev in flight at once |
| `JEV_CHUNK_CHARS` | `60000` | Files larger than this are split into `path#N` chunks |
| `JEV_MAX_ITEMS` | `500` | Refuses a call that would send more than this many items (safety cap) |

### Using both keys

If both keys are set, `JEV_PROVIDER` chooses which one to use. Set `JEV_FALLBACK=true` to use the other key when the primary fails:

```bash
claude mcp add jev -e OPENROUTER_API_KEY=or_key -e TYPESAFE_API_KEY=ts_key -e JEV_PROVIDER=openrouter -e JEV_FALLBACK=true -- jev-mcp
```

| Primary fails with | What happens |
|---|---|
| Network error, 5xx, 429/529 after one retry | That item is retried on the fallback provider |
| 401/402/403 (bad key, no credits, forbidden) | Falls back, and the primary is skipped for the rest of the call |
| 400/413/422 (the request itself is invalid) | No fallback, since the other provider would reject it too. The error is reported |

Fallback is invisible to the agent. The answers look the same, so no extra tokens are spent. If both providers fail, the error names each one.

## Limitations

Jev is a fast classifier, not a reasoning model. According to its [documentation](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md), it is weak at counting, arithmetic, date comparisons, and multi-step reasoning. It is also easily influenced by instructions hidden in the text it reads. See [docs/limitations.md](docs/limitations.md).

## Development

```bash
pip install -e .[dev]
```
```bash
git config core.hooksPath .githooks
```
```bash
pytest
```

The `pre-push` hook runs `pytest` and blocks the push if any test fails. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org); see [AGENTS.md](AGENTS.md#commits).

## License

MIT. This is an independent project, not affiliated with TypeSafe AI.
