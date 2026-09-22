from jev_mcp.compact import compact_answer, compact_response, is_unsure


def test_noul_confident():
    assert compact_answer({"type": "noul", "noul": 0.934}, 0.6) == 0.93


def test_noul_unsure():
    assert compact_answer({"type": "noul", "noul": 0.55}, 0.6) == [0.55, "?"]
    assert is_unsure({"type": "noul", "noul": 0.55}, 0.6)


def test_choice_confident():
    a = {"type": "choice", "choice": "bug", "confidence": 0.971, "probabilities": {"bug": 0.98, "feat": 0.02}}
    assert compact_answer(a, 0.6) == ["bug", 0.97]


def test_choice_unsure_includes_top_two():
    a = {
        "type": "choice",
        "choice": "bug",
        "confidence": 0.3,
        "probabilities": {"docs": 0.1, "bug": 0.5, "feat": 0.4},
    }
    assert compact_answer(a, 0.6) == ["bug", 0.3, {"bug": 0.5, "feat": 0.4}]


def test_score():
    a = {"type": "score", "score": 3.456, "confidence": 0.9, "legend": {}, "probabilities": {}}
    assert compact_answer(a, 0.6) == [3.46, 0.9]


def test_compact_response():
    resp = {"answers": {"q": {"type": "noul", "noul": 0.01}}}
    assert compact_response(resp, 0.6) == {"q": 0.01}
