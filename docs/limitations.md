# Limitations

From TypeSafe's [jev-1.13 jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md) and how this tool works:

| Area | Impact | Mitigation |
|---|---|---|
| Counting, arithmetic, numeric comparisons | Unreliable | Do these in code or in the agent, not with Jev |
| Date and time logic | Dates are read as text | Parse dates in code |
| Multi-step reasoning | Accuracy drops | Split into several simple questions |
| Literal reading | Negations and scope words are easy to misread | Word questions plainly and positively |
| Irrelevant surrounding text | Distracts the model | Use a smaller `JEV_CHUNK_CHARS` or narrower globs |
| Prompt injection in files | The model trusts what it reads | Treat answers about untrusted content as hints only |
| Chunked files | Each chunk is judged separately | Combine chunk answers yourself (e.g. "any chunk says yes") |
| Text only | No images | Not planned until Jev supports them |

## Open items

- Confirm the exact `criteria` format for `score` against the live API.
- Consider built-in chunk aggregation modes (`any` / `all` / `max`).
- Estimate token counts per chunk instead of using a character count.
