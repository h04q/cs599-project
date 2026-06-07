"""Agent 节点共享的状态与数据结构。

State 是 LangGraph 在节点之间传递的"工作记忆"，每个节点读取自己关心
的字段并向其中追加增量信息。这样 Agent 链路天然可观测：日志一打，
整条链路上下文都在一处。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages


Severity = Literal["low", "medium", "high"]
Category = Literal["bug", "security", "performance", "style"]


@dataclass(slots=True)
class Finding:
    """单个审查发现。后续在 Verifier 处会被打上 confirmed/rejected 标签。"""

    file: str
    line: int
    category: Category
    severity: Severity
    title: str
    detail: str
    suggestion: str = ""
    confirmed: bool | None = None        # True=确认 / False=误报 / None=未验证
    verifier_note: str = ""
    fix_patch: str = ""                  # Fixer 产出


def _merge_findings(
    left: list[Finding], right: list[Finding]
) -> list[Finding]:
    """LangGraph reducer：节点同时返回 findings 时按 (file,line,title) 去重合并。"""
    seen: dict[tuple, Finding] = {(f.file, f.line, f.title): f for f in left}
    for f in right:
        key = (f.file, f.line, f.title)
        if key in seen:
            # 后者覆盖前者（如 Verifier 给 Reviewer 的发现补 confirmed 标签）
            old = seen[key]
            merged = Finding(
                file=f.file,
                line=f.line,
                category=f.category,
                severity=f.severity,
                title=f.title,
                detail=f.detail or old.detail,
                suggestion=f.suggestion or old.suggestion,
                confirmed=f.confirmed if f.confirmed is not None else old.confirmed,
                verifier_note=f.verifier_note or old.verifier_note,
                fix_patch=f.fix_patch or old.fix_patch,
            )
            seen[key] = merged
        else:
            seen[key] = f
    return list(seen.values())


class ReviewState(TypedDict, total=False):
    """LangGraph 共享状态。total=False 让节点只关心自己读写的字段。"""

    workspace: str                         # 待审查的根目录绝对路径
    target_files: list[str]                # Scanner 选出的候选文件
    messages: Annotated[list, add_messages]
    findings: Annotated[list[Finding], _merge_findings]
    round_index: int                       # 当前是第几轮 review/verify
    max_rounds: int
    enable_fix: bool
    report_md: str                         # Reporter 最终产物
    error: str                             # 任意节点写入的致命错误（中断流程）


def initial_state(
    workspace: Path,
    *,
    max_rounds: int = 2,
    enable_fix: bool = True,
) -> ReviewState:
    return ReviewState(
        workspace=str(workspace.resolve()),
        target_files=[],
        messages=[],
        findings=[],
        round_index=0,
        max_rounds=max_rounds,
        enable_fix=enable_fix,
        report_md="",
        error="",
    )
