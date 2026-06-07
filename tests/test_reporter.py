"""Reporter 模板测试：不依赖 LLM，纯字符串输出可以稳定断言。"""
from __future__ import annotations

from src.agent.reporter import reporter_node
from src.agent.state import Finding, ReviewState


def _state(findings):
    return ReviewState(workspace="/tmp/x", findings=findings)


def test_reporter_renders_confirmed_only():
    findings = [
        Finding(file="a.py", line=10, category="security", severity="high",
                title="hardcoded-key", detail="d", suggestion="s", confirmed=True),
        Finding(file="a.py", line=20, category="style", severity="low",
                title="naming", detail="d", suggestion="s", confirmed=False,
                verifier_note="争议"),
    ]
    out = reporter_node(_state(findings))
    md = out["report_md"]
    assert "hardcoded-key" in md
    assert "SECURITY" in md
    assert "## 附录 A" in md
    # 被驳回的发现进了附录而不是主报告类目
    assert "## STYLE 类问题" not in md


def test_reporter_handles_empty_findings():
    out = reporter_node(_state([]))
    md = out["report_md"]
    assert "确认问题数**：0" in md
