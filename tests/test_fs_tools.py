"""文件系统工具的安全性测试：确保 sandbox 不会被相对路径绕过。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.tools.fs import make_fs_tools


def test_list_files_limits_to_workspace(tmp_path: Path):
    (tmp_path / "a.py").write_text("print(1)\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("//")
    tools = {t.name: t for t in make_fs_tools(tmp_path)}
    out = tools["list_files"].invoke({"subdir": "."})
    assert "a.py" in out
    assert "node_modules" not in out  # 噪声目录被过滤


def test_read_file_blocks_path_traversal(tmp_path: Path):
    inside = tmp_path / "ws"
    inside.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("PWNED")
    tools = {t.name: t for t in make_fs_tools(inside)}
    with pytest.raises(ValueError):
        tools["read_file"].invoke({"path": "../secret.txt"})


def test_write_patch_creates_file(tmp_path: Path):
    tools = {t.name: t for t in make_fs_tools(tmp_path)}
    res = tools["write_patch"].invoke(
        {"path": "sub/new.py", "new_content": "print('hi')\n"}
    )
    assert "OK" in res
    assert (tmp_path / "sub" / "new.py").read_text() == "print('hi')\n"
