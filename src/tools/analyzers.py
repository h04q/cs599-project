"""静态分析工具：把 pylint / bandit / radon 包成 Function Calling 工具。

调用约束：
- 全部以子进程方式调用，超时 30s，防止 Agent 卡死。
- 输出统一压缩为简短文本，避免 JSON 噪声把上下文撑爆。
- 工具失败时返回结构化错误而不是抛异常 — Agent 可据此选择换条路。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from langchain_core.tools import tool


TIMEOUT_SECONDS = 30


def _resolve(workspace: Path, target: str) -> Path:
    workspace = workspace.resolve()
    candidate = (workspace / target).resolve()
    if workspace not in candidate.parents and candidate != workspace:
        raise ValueError(f"路径越界: {target!r}")
    return candidate


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"[TIMEOUT] 命令 {' '.join(cmd)} 超过 {TIMEOUT_SECONDS}s"
    except FileNotFoundError as e:
        return 127, "", f"[NOT_FOUND] {e}"


def make_analyzer_tools(workspace: Path):
    workspace = workspace.resolve()

    @tool
    def run_pylint(path: str) -> str:
        """对 Python 文件/目录运行 pylint，返回 JSON 结果（截断为前 30 条）。"""
        if not shutil.which("pylint"):
            return "[SKIP] 未安装 pylint，跳过该工具"
        target = _resolve(workspace, path)
        rc, out, err = _run(["pylint", "-f", "json", "--score=n", str(target)])
        if rc not in (0, 1, 2, 4, 8, 16, 20, 32):  # pylint 用 bitmask 退出码
            return f"[ERROR] pylint 失败: {err.strip()[:500]}"
        try:
            issues = json.loads(out or "[]")
        except json.JSONDecodeError:
            return f"[ERROR] pylint 输出无法解析: {out[:500]}"
        compact = [
            {
                "path": Path(i.get("path", "")).name,
                "line": i.get("line"),
                "type": i.get("type"),
                "symbol": i.get("symbol"),
                "msg": i.get("message"),
            }
            for i in issues[:30]
        ]
        return json.dumps(
            {"total": len(issues), "issues": compact}, ensure_ascii=False
        )

    @tool
    def run_bandit(path: str) -> str:
        """对 Python 文件/目录运行 bandit 安全扫描，返回结构化结果。"""
        if not shutil.which("bandit"):
            return "[SKIP] 未安装 bandit，跳过该工具"
        target = _resolve(workspace, path)
        rc, out, err = _run(["bandit", "-f", "json", "-q", "-r", str(target)])
        if rc not in (0, 1):
            return f"[ERROR] bandit 失败: {err.strip()[:500]}"
        try:
            data = json.loads(out or "{}")
        except json.JSONDecodeError:
            return f"[ERROR] bandit 输出无法解析: {out[:500]}"
        results = data.get("results", [])
        compact = [
            {
                "file": Path(r.get("filename", "")).name,
                "line": r.get("line_number"),
                "severity": r.get("issue_severity"),
                "confidence": r.get("issue_confidence"),
                "test_id": r.get("test_id"),
                "msg": r.get("issue_text"),
            }
            for r in results[:30]
        ]
        return json.dumps(
            {"total": len(results), "issues": compact}, ensure_ascii=False
        )

    @tool
    def run_radon(path: str) -> str:
        """运行 radon 计算圈复杂度，定位高复杂度函数。"""
        if not shutil.which("radon"):
            return "[SKIP] 未安装 radon，跳过该工具"
        target = _resolve(workspace, path)
        rc, out, err = _run(["radon", "cc", "-s", "-j", str(target)])
        if rc != 0:
            return f"[ERROR] radon 失败: {err.strip()[:500]}"
        try:
            data = json.loads(out or "{}")
        except json.JSONDecodeError:
            return f"[ERROR] radon 输出无法解析: {out[:500]}"
        # 仅保留复杂度 >= C 级（10+）的函数
        hot: list[dict] = []
        for file_path, items in data.items():
            for it in items:
                if isinstance(it, dict) and it.get("rank", "A") >= "C":
                    hot.append(
                        {
                            "file": Path(file_path).name,
                            "name": it.get("name"),
                            "line": it.get("lineno"),
                            "complexity": it.get("complexity"),
                            "rank": it.get("rank"),
                        }
                    )
        return json.dumps(
            {"hotspots": hot[:30], "total_files": len(data)}, ensure_ascii=False
        )

    return [run_pylint, run_bandit, run_radon]
