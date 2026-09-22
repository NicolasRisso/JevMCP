# Tool reference

## `jev_ask`

Ask Jev one or more typed questions about each file or text, without the agent reading the content.

### Parameters

| Name | Type | Required | Description |
|---|---|---|---|
| `questions` | object | yes | `{id: question}`. See the question types below. |
| `paths` | string[] | no* | Files, globs (`src/**/*.py`) or directories (searched recursively). Binary files are skipped. |
| `texts` | object | no* | `{id: text}` for small inline content (e.g. command output). |
| `threshold` | number | no | Confidence below this counts as "unsure". Default `0.6`. |
| `verbose` | bool | no | Return Jev's raw answers (full probabilities, legend) instead of the compact form. |

\* At least one of `paths` / `texts` must produce some text.

### Question types

These are sent unchanged to the [TypeSafe API](https://docs.typesafe.ai/api.md).

| `type` | Use for | `criteria` |
|---|---|---|
| `noul` | Yes/no | Optional text clarifying what counts as yes |
| `choice` | One of a fixed set of options (up to 255) | `{option: description}` |
| `score` | A position on an ordered scale | List of 2–10 level descriptions, from low to high. The answer is the **0-based** level position, and fractions are allowed (e.g. `1.4` falls between the 2nd and 3rd level) |

### Compact answer format

| Question type | Confident | Unsure |
|---|---|---|
| `noul` | `0.93` (probability of yes) | `[0.55, "?"]` |
| `choice` | `["billing", 0.97]` | `["billing", 0.41, {"billing": 0.52, "refund": 0.38}]` |
| `score` | `[3.4, 0.88]` | `[3.4, 0.35, {...top 2 levels}]` |

For `noul`, confidence is calculated as `|2p − 1|`. For `choice` and `score`, it is the `confidence` value Jev returns.

### Response

Compact mode (the default) is built to cost the agent as few tokens as possible:

```json
{"root": "reviews/", "results": {"1.txt": 0.96, "2.txt": [0.51, "?"]}, "unsure": ["2.txt"]}
```

- `root` holds the directory prefix shared by all items. Item keys are relative to it. It is omitted when there is no shared prefix.
- With **one** question, each item maps directly to its answer. With several, each item maps to `{qid: answer}`.
- `unsure` is omitted when empty.
- An item that failed maps to `{"error": "..."}`. If **every** item fails with the same error (for example a bad key), the call fails once with that message instead.
- `verbose: true` returns `{results: {item: {qid: raw Jev answer}}, unsure, input_tokens}` with full paths.

Input errors (bad question, missing key, no readable text, too many items) are returned as tool errors with a readable message.

## Context budget

What an agent pays for JevMCP:

| What | When | Size |
|---|---|---|
| Tool definition | Every turn, when the server is enabled | ~1 KB (one tool, hand-written schema, no output schema) |
| Result | Per call | A few characters per answer, plus `root` and `unsure` |

Rules that keep it this way (see AGENTS.md): one tool, a terse docstring, a hand-maintained `JEV_ASK_SCHEMA`, `structured_output=False` (otherwise every result would be sent twice), and no counters in compact output.

### Tips for agents

- Put every question you have about the same files into **one** call.
- Keep instructions literal and narrow. Jev answers exactly what you ask.
- Do not use it for counting, math, dates, or multi-step reasoning.
- Open the files listed in `unsure` yourself instead of trusting those answers.
