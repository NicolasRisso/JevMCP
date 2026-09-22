"""Shrink Jev answers so they cost the calling agent as few tokens as possible.

Compact forms:
  noul          -> 0.93                 (P(yes)); [0.55, "?"] when unsure
  choice        -> ["billing", 0.97]    ([value, confidence])
  score         -> [3.4, 0.88]
  unsure c/s    -> ["billing", 0.41, {"billing": 0.52, "refund": 0.38}]  (top-2 probabilities)

"Unsure" means confidence below `threshold`. For noul, confidence is |2p - 1|.
"""

from __future__ import annotations

from typing import Any

UNSURE = "?"


def _r(x: float) -> float:
    return round(float(x), 2)


def compact_answer(answer: dict[str, Any], threshold: float) -> Any:
    kind = answer.get("type")
    if kind == "noul":
        p = _r(answer["noul"])
        return p if abs(2 * p - 1) >= threshold else [p, UNSURE]

    value = answer["choice"] if kind == "choice" else _r(answer["score"])
    confidence = _r(answer["confidence"])
    if confidence >= threshold:
        return [value, confidence]
    top = sorted(answer.get("probabilities", {}).items(), key=lambda kv: -kv[1])[:2]
    return [value, confidence, {k: _r(v) for k, v in top}]


def is_unsure(answer: dict[str, Any], threshold: float) -> bool:
    if answer.get("type") == "noul":
        return abs(2 * answer["noul"] - 1) < threshold
    return answer["confidence"] < threshold


def compact_response(response: dict[str, Any], threshold: float) -> dict[str, Any]:
    return {qid: compact_answer(a, threshold) for qid, a in response["answers"].items()}
