# Architecture

```
src/jev_mcp/
  server.py    MCP tool definitions (MCPServer, mcp 2.x), validation, batch orchestration
  client.py    Async HTTP client for POST /v1/systemone, with retries on 429/529
  sources.py   paths/globs/dirs/texts -> (id, text) items; binary skip; chunking
  compact.py   Converts raw Jev answers into short, token-cheap values
  config.py    Settings read from environment variables
```

## Request flow

1. `jev_ask` validates the questions (type, instructions, criteria).
2. `sources.iter_items` expands the paths and splits oversized text on newline boundaries into pieces of at most `JEV_CHUNK_CHARS` characters. Chunked items get ids like `file#0`.
3. `run_batch` sends one request per item. Each request carries **all** the questions, because Jev answers them in parallel. Concurrency is capped by a semaphore of size `JEV_CONCURRENCY`.
4. Answers are compacted (see `docs/tools.md`), and items with any unsure answer are listed in `unsure`.
5. A failure on one item is recorded as `{"error": ...}` and does not fail the whole batch.

## Design principles

- **The agent's context is the scarce resource.** Every byte the tool returns costs the agent tokens, so keep output compact by default.
- **The agent never has to read the raw data.** Tools take references (paths, globs), not pasted content.
- **Uncertainty is passed on, not hidden.** Unsure answers carry enough detail for the agent to decide whether to check the item itself.

## Jev API facts this relies on

(Checked against docs.typesafe.ai, September 2026.)

- Endpoint: `POST https://api.typesafe.ai/v1/systemone` with the header `Authorization: Bearer <key>`.
- Request: `{model, state, questions: {id: {type, instructions, criteria}}}`.
- Response: `{model, answers: {id: {type, noul | choice | score, probabilities, confidence, legend}}, usage}`.
- Limits: 64k tokens per request, of which 32k is for the state plus the longest question. Up to 255 choice options. Score takes 2–10 levels.
- Rate limits: 1,200 requests per minute and 250k tokens per second (these change dynamically).
