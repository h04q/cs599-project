"""LangGraph 路由测试：should_loop_back 在不同 round / pending 组合下的行为。"""
from __future__ import annotations

from src.agent.state import Finding
from src.graph import should_loop_back


def _state(round_index: int, max_rounds: int, pending: int, confirmed: int):
    findings: list[Finding] = []
    for i in range(pending):
        findings.append(
            Finding(
                file="a.py", line=i + 1, category="bug", severity="medium",
                title=f"P{i}", detail="", confirmed=None,
            )
        )
    for i in range(confirmed):
        findings.append(
            Finding(
                file="a.py", line=100 + i, category="bug", severity="medium",
                title=f"C{i}", detail="", confirmed=True,
            )
        )
    return {
        "findings": findings,
        "round_index": round_index,
        "max_rounds": max_rounds,
    }


def test_loop_back_when_pending_and_room():
    assert should_loop_back(_state(1, 3, pending=2, confirmed=0)) == "reviewer"


def test_proceed_to_fixer_when_max_rounds():
    assert should_loop_back(_state(3, 3, pending=2, confirmed=0)) == "fixer"


def test_proceed_to_fixer_when_no_pending():
    assert should_loop_back(_state(1, 3, pending=0, confirmed=5)) == "fixer"
