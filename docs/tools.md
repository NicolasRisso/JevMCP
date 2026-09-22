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
| `score` | A position on an ordered scale | 2–10 level descriptions, from low to high |

### Compact answer format

| Question type | Confident | Unsure |
|---|---|---|
| `noul` | `0.93` (probability of yes) | `[0.55, "?"]` |
| `choice` | `["billing", 0.97]` | `["billing", 0.41, {"billing": 0.52, "refund": 0.38}]` |
| `score` | `[3.4, 0.88]` | `[3.4, 0.35, {...top 2 levels}]` |

For `noul`, confidence is calculated as `|2p − 1|`. For `choice` and `score`, it is the `confidence` value Jev returns.

### Response

```json
{"results": {"<item>": {"<qid>": "<answer>"}}, "unsure": ["<item>"], "items": 3, "input_tokens": 1234}
```

If a single item fails, its entry is `{"error": "..."}` and the rest of the batch still returns.

### Tips for agents

- Put every question you have about the same files into **one** call.
- Keep instructions literal and narrow. Jev answers exactly what you ask.
- Do not use it for counting, math, dates, or multi-step reasoning.
- Open the files listed in `unsure` yourself instead of trusting those answers.
