"""Verifier Agent：对抗式验证，把 Reviewer 的发现尽可能"驳倒"。

我们要的不是"再夸一遍发现"，而是要一个怀疑论者——它的目标是证伪。
只有它驳不倒的发现才会进入 Fixer / Reporter。这能显著降低 LLM 的
"过度报告"倾向。
"""
from __future__ import annotations

from pathlib import Path

from src.observability import get_logger

from .llm_helpers import call_llm_json
from .state import Finding, ReviewState


_log = get_logger("agent.verifier")


SYSTEM_PROMPT = """你是严格的代码审查质检员 (Adversarial Verifier)。
你的唯一目标是**驳倒**输入的每一条 finding：
- 若证据不足、行号不对、属于风格争议、或在该语境下并非真正问题，请标 confirmed=false。
- 默认倾向 confirmed=false，只有确信是真问题时才 confirmed=true。
- 输出 JSON 数组，每项格式：{"index": <原序号>, "confirmed": <bool>, "note": "<理由 ≤ 2 句>"}。
- 不要修改 finding 的其他字段；只输出 index/confirmed/note。
"""


def verifier_node(state: ReviewState) -> dict:
    findings = state.get("findings", [])
    pending = [f for f in findings if f.confirmed is None]
    if not pending:
        return {"messages": [("system", "[Verifier] 无新增 finding 待验证")]}

    workspace = Path(state["workspace"])
    ws_root = workspace if workspace.is_dir() else workspace.parent
    file_cache: dict[str, str] = {}

    payload = _build_payload(pending, ws_root, file_cache)
    raw = call_llm_json(SYSTEM_PROMPT, payload, agent_name="verifier")
    if not isinstance(raw, list):
        _log.warning("verifier_no_list")
        return {
            "messages": [("system", "[Verifier] LLM 输出无法解析，保守地标记全部确认")]
        }

    verdicts: dict[int, tuple[bool, str]] = {}
    for v in raw:
        try:
            idx = int(v.get("index"))
            verdicts[idx] = (bool(v.get("confirmed")), str(v.get("note", "")))
        except Exception:  # noqa: BLE001
            continue

    updated: list[Finding] = []
    for i, f in enumerate(pending):
        confirmed, note = verdicts.get(i, (True, "(verifier 未给出意见，保守保留)"))
        updated.append(
            Finding(
                file=f.file,
                line=f.line,
                category=f.category,
                severity=f.severity,
                title=f.title,
                detail=f.detail,
                suggestion=f.suggestion,
                confirmed=confirmed,
                verifier_note=note,
            )
        )

    confirmed_count = sum(1 for f in updated if f.confirmed)
    _log.info(
        "verifier_done",
        total=len(updated),
        confirmed=confirmed_count,
        rejected=len(updated) - confirmed_count,
    )
    return {
        "findings": updated,
        "round_index": state.get("round_index", 0) + 1,
        "messages": [
            (
                "system",
                f"[Verifier] {confirmed_count}/{len(updated)} 条被确认为真问题",
            )
        ],
    }


def _build_payload(
    findings: list[Finding], ws_root: Path, cache: dict[str, str]
) -> str:
    lines_out: list[str] = ["## 待验证的 findings："]
    for i, f in enumerate(findings):
        snippet = _file_snippet(ws_root, f.file, f.line, cache)
        lines_out.append(
            f"\n### #{i} [{f.category}/{f.severity}] {f.title}\n"
            f"- file: {f.file}:{f.line}\n"
            f"- detail: {f.detail}\n"
            f"- suggestion: {f.suggestion}\n"
            f"- 上下文:\n{snippet}"
        )
    lines_out.append(
        "\n请输出 JSON 数组，对每条 finding 给出 confirmed / note。"
    )
    return "\n".join(lines_out)


def _file_snippet(
    ws_root: Path, rel_path: str, line: int, cache: dict[str, str], window: int = 6
) -> str:
    text = cache.get(rel_path)
    if text is None:
        p = (ws_root / rel_path).resolve()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            text = ""
        cache[rel_path] = text
    if not text:
        return "(无法读取)"
    lines = text.splitlines()
    s = max(0, line - 1 - window)
    e = min(len(lines), line - 1 + window + 1)
    return "\n".join(f"{i + 1:>5}: {lines[i]}" for i in range(s, e))
