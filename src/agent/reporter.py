"""Reporter Agent：把所有 confirmed finding 汇总为 Markdown 报告。

Reporter 不调用 LLM，纯模板渲染——这样报告格式可预期、可测试、可
被 CI 用脚本断言。LLM 写报告很容易"花活"，作业评分场景反而不利。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from .state import Finding, ReviewState


SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def reporter_node(state: ReviewState) -> dict:
    findings = state.get("findings", [])
    confirmed = [f for f in findings if f.confirmed]
    rejected = [f for f in findings if f.confirmed is False]

    workspace = state.get("workspace", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = _render(workspace, timestamp, confirmed, rejected)
    return {
        "report_md": md,
        "messages": [
            ("system", f"[Reporter] 报告生成完毕（{len(confirmed)} 条确认问题）")
        ],
    }


def _render(
    workspace: str,
    timestamp: str,
    confirmed: list[Finding],
    rejected: list[Finding],
) -> str:
    by_cat: dict[str, list[Finding]] = defaultdict(list)
    for f in confirmed:
        by_cat[f.category].append(f)
    sev_counter = Counter(f.severity for f in confirmed)

    lines: list[str] = [
        "# CodeSentinel 审查报告",
        "",
        f"- **审查目标**：`{workspace}`",
        f"- **生成时间**：{timestamp}",
        f"- **确认问题数**：{len(confirmed)}（high={sev_counter.get('high', 0)}, "
        f"medium={sev_counter.get('medium', 0)}, low={sev_counter.get('low', 0)}）",
        f"- **被对抗式验证驳回**：{len(rejected)}",
        "",
        "## 概要",
        "",
        "| 类别 | 数量 |",
        "| --- | --- |",
    ]
    for cat in ("bug", "security", "performance", "style"):
        lines.append(f"| {cat} | {len(by_cat.get(cat, []))} |")
    lines.append("")

    for cat in ("bug", "security", "performance", "style"):
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"## {cat.upper()} 类问题")
        lines.append("")
        items.sort(key=lambda x: (SEV_ORDER.get(x.severity, 9), x.file, x.line))
        for i, f in enumerate(items, 1):
            lines.extend(
                [
                    f"### {i}. [{f.severity}] {f.title}",
                    "",
                    f"- 位置：`{f.file}:{f.line}`",
                    f"- 问题：{f.detail}",
                    f"- 建议：{f.suggestion}",
                    f"- 验证员备注：{f.verifier_note or '—'}",
                    "",
                ]
            )
            if f.fix_patch:
                lines.extend(
                    [
                        "<details><summary>自动修复摘要</summary>",
                        "",
                        "```",
                        f.fix_patch,
                        "```",
                        "",
                        "</details>",
                        "",
                    ]
                )

    if rejected:
        lines.append("## 附录 A：被驳回的发现（仅供复核）")
        lines.append("")
        for f in rejected:
            lines.append(
                f"- `{f.file}:{f.line}` **{f.title}** — {f.verifier_note}"
            )
        lines.append("")

    lines.append("---")
    lines.append("_本报告由 CodeSentinel Agentic Pipeline 自动生成。_")
    return "\n".join(lines)
