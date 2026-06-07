"""LangGraph 状态机：把 Agent 节点编排成可运行的工作流。

整体拓扑：
    START → scanner → reviewer → verifier ─┐
                       ↑                    │
                       └─ (round < max && 有未确认) ─┘
                                            │
                                            ↓
                                          fixer → reporter → END

关键设计：
- 条件路由 should_loop_back：在 verifier 之后判断是否还需要再来一轮，
  实现"多步推理"。MVP 默认 max_rounds=2，避免 LLM 无限循环烧钱。
- 节点之间通过 ReviewState 传递增量；reducer (`add_messages`、
  `_merge_findings`) 负责合并。
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agent import (
    ReviewState,
    fixer_node,
    reporter_node,
    reviewer_node,
    scanner_node,
    verifier_node,
)


def should_loop_back(state: ReviewState) -> str:
    """Verifier 后的路由：如果还有未确认的发现且未达上限，回 reviewer 再补一轮。"""
    findings = state.get("findings", [])
    pending = [f for f in findings if f.confirmed is None]
    round_index = state.get("round_index", 0)
    max_rounds = state.get("max_rounds", 2)
    if pending and round_index < max_rounds:
        return "reviewer"
    return "fixer"


def build_graph():
    g = StateGraph(ReviewState)
    g.add_node("scanner", scanner_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("verifier", verifier_node)
    g.add_node("fixer", fixer_node)
    g.add_node("reporter", reporter_node)

    g.add_edge(START, "scanner")
    g.add_edge("scanner", "reviewer")
    g.add_edge("reviewer", "verifier")
    g.add_conditional_edges(
        "verifier",
        should_loop_back,
        {"reviewer": "reviewer", "fixer": "fixer"},
    )
    g.add_edge("fixer", "reporter")
    g.add_edge("reporter", END)
    return g.compile()


__all__ = ["build_graph", "should_loop_back"]
