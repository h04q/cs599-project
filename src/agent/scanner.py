"""Scanner Agent：枚举待审查文件 + 跑静态分析做"先验线索"。

Scanner 是整条链路的第一步，目标是把"什么文件值得审 + 静态工具已经
能告诉我们什么"两件事在 LLM 介入之前先做完，省 token 也降误报。
"""
from __future__ import annotations

from pathlib import Path

from src.observability import get_logger
from src.tools.analyzers import make_analyzer_tools
from src.tools.fs import TEXT_EXTENSIONS

from .state import ReviewState


_log = get_logger("agent.scanner")
_MAX_FILES = 20  # MVP 阶段对单次审查规模设上限


def scanner_node(state: ReviewState) -> dict:
    workspace = Path(state["workspace"])
    files = _collect_files(workspace)
    _log.info("scanner_files", count=len(files), files=files[:5])

    analyzer_hints = _run_analyzers(workspace, files)

    msg = (
        f"[Scanner] 选出 {len(files)} 个文件待审查；"
        f"静态分析提示：\n{analyzer_hints}"
    )
    return {
        "target_files": files,
        "messages": [("system", msg)],
    }


def _collect_files(workspace: Path) -> list[str]:
    if workspace.is_file():
        return [workspace.name]
    out: list[str] = []
    for p in workspace.rglob("*"):
        if len(out) >= _MAX_FILES:
            break
        if not p.is_file() or p.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        parts = set(p.relative_to(workspace).parts)
        if parts & {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build"}:
            continue
        out.append(p.relative_to(workspace).as_posix())
    return out


def _run_analyzers(workspace: Path, files: list[str]) -> str:
    """对单文件 / 整目录跑一次静态分析，把结果浓缩为一段提示文本。"""
    if workspace.is_file():
        ws_root = workspace.parent
        target = workspace.name
    else:
        ws_root = workspace
        target = "."

    tools = {t.name: t for t in make_analyzer_tools(ws_root)}
    parts: list[str] = []
    for name in ("run_pylint", "run_bandit", "run_radon"):
        try:
            res = tools[name].invoke({"path": target})
            parts.append(f"== {name} ==\n{res}")
        except Exception as e:  # noqa: BLE001 — 工具失败不该中断流程
            parts.append(f"== {name} 失败：{e} ==")
    return "\n\n".join(parts)
