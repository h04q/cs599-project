"""文件系统工具：列目录、读文件、写补丁。

约束：
- 所有路径都被 sandbox 到一个 workspace 根目录下，防止 LLM 通过相对路径
  逃逸到敏感系统目录（学术作业级别的最低安全防线）。
- 读文件做最大字节数限制，避免一次喂给 LLM 几兆的二进制。
"""
from __future__ import annotations

import os
from pathlib import Path

from langchain_core.tools import tool


MAX_FILE_BYTES = 200_000  # ~200KB，单文件超过则截断
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c",
    ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".kt", ".swift",
    ".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg",
}


def _resolve_safe(workspace: Path, target: str) -> Path:
    """把 target 解析到 workspace 内的绝对路径，越界则抛错。"""
    workspace = workspace.resolve()
    candidate = (workspace / target).resolve()
    if workspace not in candidate.parents and candidate != workspace:
        raise ValueError(
            f"路径越界: {target!r} 不在 workspace {workspace!s} 之内"
        )
    return candidate


def make_fs_tools(workspace: Path):
    """绑定 workspace 后返回 LangChain 工具列表，便于 Agent 注册。"""
    workspace = workspace.resolve()

    @tool
    def list_files(subdir: str = ".", max_items: int = 200) -> str:
        """列出 workspace 下指定子目录的文件，仅返回文本类源代码文件。

        Args:
            subdir: 相对 workspace 的子目录，默认根目录
            max_items: 返回上限，避免巨型仓库刷屏
        """
        root = _resolve_safe(workspace, subdir)
        if root.is_file():
            return root.relative_to(workspace).as_posix()

        results: list[str] = []
        for p in root.rglob("*"):
            if len(results) >= max_items:
                break
            if not p.is_file():
                continue
            if p.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            # 跳过常见噪声目录
            parts = set(p.relative_to(workspace).parts)
            if parts & {"node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build"}:
                continue
            results.append(p.relative_to(workspace).as_posix())
        return "\n".join(results) if results else "(没有匹配的文件)"

    @tool
    def read_file(path: str, start_line: int = 1, end_line: int = 0) -> str:
        """读取 workspace 内指定文件的内容。

        Args:
            path: 相对 workspace 的文件路径
            start_line: 起始行（1-based）
            end_line: 结束行；0 表示读到末尾
        """
        target = _resolve_safe(workspace, path)
        if not target.is_file():
            return f"[ERROR] 文件不存在: {path}"
        size = target.stat().st_size
        if size > MAX_FILE_BYTES:
            return (
                f"[WARN] 文件 {path} 大小 {size} 字节，超过 {MAX_FILE_BYTES} 限制，"
                "建议分段读取或先做静态分析定位行号。"
            )
        text = target.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        s = max(1, start_line) - 1
        e = len(lines) if end_line <= 0 else min(end_line, len(lines))
        chunk = lines[s:e]
        numbered = "\n".join(f"{i + s + 1:>5}: {line}" for i, line in enumerate(chunk))
        return numbered or "(空文件)"

    @tool
    def write_patch(path: str, new_content: str) -> str:
        """覆盖写入文件。仅在 ENABLE_AUTO_FIX=true 时由 Fixer Agent 调用。

        Args:
            path: 相对 workspace 的文件路径
            new_content: 完整新内容（不是 diff）
        """
        target = _resolve_safe(workspace, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding="utf-8")
        return f"[OK] 已写入 {path}（{len(new_content)} 字节）"

    return [list_files, read_file, write_patch]
