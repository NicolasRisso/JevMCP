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

```bash
pip install git+https://github.com/NicolasRisso/JevMCP
```

You need **one** API key. Either one works:

- **TypeSafe directly:** get a key at https://console.typesafe.ai/keys
  ```bash
  claude mcp add jev -e TYPESAFE_API_KEY=your_key -- jev-mcp
  ```
- **OpenRouter:** use your existing OpenRouter key. Jev is served through OpenRouter's alpha Decisions endpoint.
  ```bash
  claude mcp add jev -e OPENROUTER_API_KEY=your_key -- jev-mcp
  ```

For any other MCP client, run `jev-mcp` over stdio with one of those keys set.

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
| `JEV_PROVIDER` | auto | `typesafe` or `openrouter`. Auto picks TypeSafe if its key is set, otherwise OpenRouter |
| `JEV_MODEL` | `jev-latest` / `typesafe/jev-1.13` | Model name sent to the API (TypeSafe / OpenRouter default) |
| `JEV_API_URL` | provider's endpoint | Override the endpoint URL |
| `JEV_CONCURRENCY` | `16` | Max requests to Jev in flight at once |
| `JEV_CHUNK_CHARS` | `60000` | Files larger than this are split into `path#N` chunks |
| `JEV_MAX_ITEMS` | `500` | Refuses a call that would send more than this many items (safety cap) |

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
