"""Agent 工具集：所有 Function Calling 入口的统一注册点。"""
from __future__ import annotations

from pathlib import Path

from .analyzers import make_analyzer_tools
from .fs import make_fs_tools
from .git import make_git_tools


def build_all_tools(workspace: Path) -> list:
    """把 workspace 绑定到每个工具上，返回 LangChain Tool 列表。"""
    return [
        *make_fs_tools(workspace),
        *make_analyzer_tools(workspace),
        *make_git_tools(workspace),
    ]


__all__ = ["build_all_tools", "make_fs_tools", "make_analyzer_tools", "make_git_tools"]
