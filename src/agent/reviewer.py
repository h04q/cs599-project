"""Reviewer Agent：对每个候选文件做多维度审查，产出 Findings。

为什么按"维度"拆而不是按"文件"拆？
- 同一维度的关注点高度一致，prompt 一次写好就能复用，LLM 也更聚焦。
- 后续 Verifier 同样按发现去验证，维度标签可直接用于报告分类。
"""
from __future__ import annotations

from pathlib import Path

from src.observability import get_logger

from .llm_helpers import call_llm_json
from .state import Category, Finding, ReviewState


_log = get_logger("agent.reviewer")


REVIEW_DIMENSIONS: dict[Category, str] = {
    "bug": "潜在 bug、空指针、未处理异常、错误的边界条件、并发问题、资源泄漏。",
    "security": "代码注入、不安全反序列化、硬编码密钥、未校验输入、SSRF/XSS、危险函数调用（eval/exec/pickle）。",
    "performance": "明显的 O(n²)、不必要的循环嵌套、IO 阻塞、缓存缺失。",
    "style": "命名歧义、超长函数、坏味道、文档缺失。仅在严重影响可维护性时报告。",
}


SYSTEM_PROMPT = """你是资深代码审查工程师 (Senior Code Reviewer)。
你只负责针对给定**单一维度**输出审查发现。

要求：
1. 严格输出 JSON 数组，每项包含 file/line/category/severity/title/detail/suggestion。
2. severity ∈ {low, medium, high}。
3. 若没有发现，输出 []。
4. 不要编造行号；不确定就给最接近的行。
5. detail 解释"为什么是问题"，suggestion 解释"怎么改"，各 ≤ 2 句话。
6. 不要复述源代码本身，只输出结论。
"""


def reviewer_node(state: ReviewState) -> dict:
    workspace = Path(state["workspace"])
    files = state.get("target_files", [])
    if not files:
        return {"messages": [("system", "[Reviewer] 没有可审文件，跳过")]}

    findings: list[Finding] = []
    file_blob = _read_files_for_prompt(workspace, files)

    for cat, focus in REVIEW_DIMENSIONS.items():
        user_prompt = _build_prompt(cat, focus, file_blob)
        raw = call_llm_json(
            SYSTEM_PROMPT, user_prompt, agent_name=f"reviewer:{cat}"
        )
        if not isinstance(raw, list):
            _log.warning("reviewer_no_list", category=cat)
            continue
        for item in raw:
            try:
                findings.append(
                    Finding(
                        file=str(item.get("file") or files[0]),
                        line=int(item.get("line") or 1),
                        category=cat,
                        severity=str(item.get("severity") or "medium").lower(),  # type: ignore[arg-type]
                        title=str(item.get("title") or "(no title)"),
                        detail=str(item.get("detail") or ""),
                        suggestion=str(item.get("suggestion") or ""),
                    )
                )
            except Exception as e:  # noqa: BLE001 — 单条解析失败不影响其他
                _log.warning("reviewer_item_skip", error=str(e), item=item)

    _log.info("reviewer_done", findings=len(findings))
    return {
        "findings": findings,
        "messages": [
            ("system", f"[Reviewer] 共发现 {len(findings)} 条待验证 issue")
        ],
    }


def _read_files_for_prompt(
    workspace: Path, files: list[str], max_chars: int = 8000
) -> str:
    """把候选文件拼成一个块，超过预算时尾部截断，并标注。"""
    ws_root = workspace if workspace.is_dir() else workspace.parent
    chunks: list[str] = []
    budget = max_chars
    for f in files:
        p = (ws_root / f).resolve()
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        head = f"### FILE: {f}\n"
        body = "\n".join(
            f"{i + 1:>5}: {line}" for i, line in enumerate(text.splitlines())
        )
        block = head + body + "\n"
        if len(block) > budget:
            chunks.append(block[: budget] + "\n[...TRUNCATED]")
            break
        chunks.append(block)
        budget -= len(block)
    return "\n".join(chunks) or "(空)"


def _build_prompt(cat: Category, focus: str, file_blob: str) -> str:
    return (
        f"## 维度：{cat}\n"
        f"## 关注点：{focus}\n\n"
        "## 待审代码（已带行号）：\n"
        f"{file_blob}\n\n"
        "请输出 JSON 数组。"
    )
