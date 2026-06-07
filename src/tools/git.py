"""Git 相关工具：diff / log / show。

仅做只读操作，不允许 Agent 直接 commit/push — 修复以工作区写入为准，
是否提交交给人。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from langchain_core.tools import tool


def _git(cwd: Path, *args: str, timeout: int = 15) -> tuple[int, str, str]:
    if not shutil.which("git"):
        return 127, "", "[NOT_FOUND] 未安装 git"
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "[TIMEOUT]"


def make_git_tools(workspace: Path):
    workspace = workspace.resolve()

    @tool
    def git_diff(rev: str = "HEAD") -> str:
        """查看当前工作区相对指定 revision 的 diff。常用于 PR 审查。"""
        rc, out, err = _git(workspace, "diff", rev, "--unified=3")
        if rc != 0:
            return f"[ERROR] git diff: {err.strip()[:500]}"
        return out[:8000] or "(无变更)"

    @tool
    def git_log(limit: int = 10) -> str:
        """查看最近 N 条提交，用于理解变更历史。"""
        rc, out, err = _git(
            workspace, "log", f"-{limit}", "--oneline", "--no-decorate"
        )
        if rc != 0:
            return f"[ERROR] git log: {err.strip()[:500]}"
        return out or "(无提交)"

    return [git_diff, git_log]
