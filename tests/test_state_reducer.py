"""ReviewState reducer 行为测试：findings 合并 + verifier 标签覆盖。"""
from __future__ import annotations

from src.agent.state import Finding, _merge_findings


def _f(line: int, title: str = "X", **kw) -> Finding:
    base = {
        "file": "a.py",
        "line": line,
        "category": "bug",
        "severity": "medium",
        "title": title,
        "detail": "d",
    }
    base.update(kw)
    return Finding(**base)


def test_merge_dedupes_same_position_and_title():
    left = [_f(1, "X")]
    right = [_f(1, "X"), _f(2, "Y")]
    merged = _merge_findings(left, right)
    assert len(merged) == 2


def test_merge_lets_verifier_overwrite_confirmed():
    left = [_f(1, "X")]                                  # confirmed=None
    right = [_f(1, "X", confirmed=True, verifier_note="OK")]
    merged = _merge_findings(left, right)
    assert len(merged) == 1
    assert merged[0].confirmed is True
    assert merged[0].verifier_note == "OK"


def test_merge_keeps_unique_titles_at_same_line():
    left = [_f(1, "X")]
    right = [_f(1, "Y")]
    merged = _merge_findings(left, right)
    assert len(merged) == 2
