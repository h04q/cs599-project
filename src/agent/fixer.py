"""Fixer Agent：对已确认的 finding 生成最小修复 Patch。

设计选择：
- 只对 confirmed=True 的 finding 出 patch，避免给误报修代码。
- 输出"完整新文件内容"，不输出 unified diff —— LLM 在生成 diff 时
  常常算错行号，全文件覆盖更稳定（代价是 token 多一些）。
- 同一文件的多个 finding 打包在一个 prompt 里一次性修复，避免后一次
  覆盖前一次的改动。
- 写盘动作交给 write_patch 工具，本节点自身不直接 touch 文件系统，
  方便测试时 mock。
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from src.observability import MemoryRecord, MemoryStore, get_logger
from src.tools.fs import make_fs_tools

from .llm_helpers import call_llm_json
from .state import Finding, ReviewState


_log = get_logger("agent.fixer")


SYSTEM_PROMPT = """你是资深 Bug 修复工程师。
针对给定的所有 findings，请一次性修复并输出修复后的**完整文件内容**。
- 输出 JSON：{"new_content": "<完整内容>", "fix_strategy": "<一句话总结修复策略>"}
- 不要 ``` 包裹 new_content 的代码本身（只在最外层 JSON 用引号即可）。
- 必须修复列出的所有问题，不要遗漏。
- 不要顺手重构与 findings 无关的位置。
- 保持原文件的缩进风格、编码、行尾。
"""


def fixer_node(state: ReviewState) -> dict:
    if not state.get("enable_fix"):
        return {"messages": [("system", "[Fixer] enable_fix=false，跳过修复阶段")]}

    findings = state.get("findings", [])
    confirmed = [f for f in findings if f.confirmed and not f.fix_patch]
    if not confirmed:
        return {"messages": [("system", "[Fixer] 没有需要修复的 confirmed finding")]}

    workspace = Path(state["workspace"])
    ws_root = workspace if workspace.is_dir() else workspace.parent
    fs_tools = {t.name: t for t in make_fs_tools(ws_root)}
    memory = MemoryStore()

    # 按文件分组，同一文件的所有 finding 一次性修复
    by_file: dict[str, list[Finding]] = defaultdict(list)
    for f in confirmed:
        by_file[f.file].append(f)

    updated: list[Finding] = []
    for file_path, file_findings in by_file.items():
        prior_hints = []
        for f in file_findings:
            prior = memory.recall(_pattern_key(f))
            if prior:
                prior_hints.append(f"- {f.title}: {prior[0].fix_strategy}")

        prior_hint = (
            "历史经验:\n" + "\n".join(prior_hints)
            if prior_hints
            else "（无历史经验可参考）"
        )

        user_prompt = _build_batch_prompt(ws_root, file_path, file_findings, prior_hint)
        raw = call_llm_json(SYSTEM_PROMPT, user_prompt, agent_name="fixer")
        if not isinstance(raw, dict):
            _log.warning("fixer_no_dict", file=file_path)
            continue
        new_content = str(raw.get("new_content") or "")
        strategy = str(raw.get("fix_strategy") or "")
        if not new_content:
            continue

        # 通过工具写盘，保证沙箱与日志一致
        result = fs_tools["write_patch"].invoke(
            {"path": file_path, "new_content": new_content}
        )
        _log.info(
            "fixer_applied",
            file=file_path,
            findings_count=len(file_findings),
            result=result,
        )

        for f in file_findings:
            memory.remember(
                MemoryRecord(
                    pattern=_pattern_key(f),
                    description=f.title,
                    fix_strategy=strategy,
                    severity=f.severity,
                    accepted=True,
                    created_at="",
                )
            )
            updated.append(
                Finding(
                    file=f.file,
                    line=f.line,
                    category=f.category,
                    severity=f.severity,
                    title=f.title,
                    detail=f.detail,
                    suggestion=f.suggestion,
                    confirmed=f.confirmed,
                    verifier_note=f.verifier_note,
                    fix_patch=new_content[:200] + "...(已写入)",
                )
            )

    return {
        "findings": updated,
        "messages": [
            ("system", f"[Fixer] 已生成并写入 {len(updated)} 份修复")
        ],
    }


def _pattern_key(f: Finding) -> str:
    return f"{f.category}:{_norm_title(f.title)}"


def _norm_title(title: str) -> str:
    return "-".join(title.lower().split())[:60]


def _build_batch_prompt(
    ws_root: Path, file_path: str, findings: list[Finding], prior_hint: str
) -> str:
    p = (ws_root / file_path).resolve()
    try:
        original = p.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        original = "(无法读取原文件)"

    findings_desc = []
    for i, f in enumerate(findings, 1):
        findings_desc.append(
            f"### Finding #{i}\n"
            f"- 类别/严重度：{f.category} / {f.severity}\n"
            f"- 位置：{f.file}:{f.line}\n"
            f"- 标题：{f.title}\n"
            f"- 详情：{f.detail}\n"
            f"- 建议：{f.suggestion}\n"
            f"- 验证员备注：{f.verifier_note}"
        )

    return (
        f"## 需要修复的问题（共 {len(findings)} 条，必须全部修复）\n\n"
        + "\n\n".join(findings_desc)
        + f"\n\n## {prior_hint}\n\n"
        + f"## 原文件内容\n```\n{original}\n```\n\n"
        + "请一次性修复以上所有问题，输出 JSON: { \"new_content\": ..., \"fix_strategy\": ... }"
    )
