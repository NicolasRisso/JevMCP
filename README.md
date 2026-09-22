# JevMCP

An open-source [MCP](https://modelcontextprotocol.io) server that lets coding agents (Claude Code, Cursor, etc.) hand off **yes/no, enum and scale judgements** to [TypeSafe's Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev) model.

Why use it: an agent that has to answer "which of these 300 files mention X?" normally reads all 300 files into its context. With JevMCP, **Jev reads the files** and the agent only gets back a compact table of answers with confidence scores. That uses fewer tokens, runs faster, and costs very little (Jev charges $0.042 per million input tokens).

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

Get an API key at https://console.typesafe.ai/keys, then register the server with Claude Code:

```bash
claude mcp add jev -e TYPESAFE_API_KEY=your_key -- jev-mcp
```

For any other MCP client, run `jev-mcp` over stdio with `TYPESAFE_API_KEY` set.

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

Returns:

```json
{"results":{"reviews/1.txt":{"mentions_cleanliness":0.96,"sentiment":["positive",0.94]},
            "reviews/2.txt":{"mentions_cleanliness":[0.51,"?"],"sentiment":["mixed",0.42,{"mixed":0.5,"negative":0.41}]}},
 "unsure":["reviews/2.txt"],"items":2,"input_tokens":812}
```

See [docs/tools.md](docs/tools.md) for the full tool reference.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `TYPESAFE_API_KEY` | (required) | Your TypeSafe API key |
| `JEV_MODEL` | `jev-latest` | Model name sent to the API |
| `JEV_API_URL` | `https://api.typesafe.ai/v1/systemone` | API endpoint |
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
