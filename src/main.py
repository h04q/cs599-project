"""CodeSentinel CLI 入口。

使用方式：
    python -m src.main review --path ./examples/sample_buggy.py
    python -m src.main review --path ./your_repo --output report.md
    python -m src.main info
"""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agent import initial_state
from src.config import get_settings
from src.graph import build_graph
from src.observability import configure_logging, get_logger


app = typer.Typer(
    add_completion=False,
    help="CodeSentinel — 智能代码审查与 Bug 修复 Agent",
)
console = Console()


@app.command()
def review(
    path: Path = typer.Option(..., "--path", "-p", help="待审查文件或目录"),
    output: Path = typer.Option(
        Path("report.md"), "--output", "-o", help="报告输出路径"
    ),
    max_rounds: int = typer.Option(
        0, "--max-rounds", help="0 表示用 .env 里的默认值"
    ),
    no_fix: bool = typer.Option(
        False, "--no-fix", help="只审查不自动修复"
    ),
) -> None:
    """对给定路径执行 Agentic 代码审查。"""
    configure_logging()
    log = get_logger("cli")
    s = get_settings()

    if not path.exists():
        console.print(f"[red]路径不存在：{path}[/red]")
        raise typer.Exit(code=2)

    rounds = max_rounds or s.max_review_rounds
    enable_fix = (not no_fix) and s.enable_auto_fix

    console.print(
        Panel.fit(
            f"workspace=[cyan]{path.resolve()}[/cyan]\n"
            f"provider=[green]{s.llm_provider}[/green]  "
            f"max_rounds={rounds}  enable_fix={enable_fix}",
            title="CodeSentinel",
            border_style="cyan",
        )
    )

    state = initial_state(path, max_rounds=rounds, enable_fix=enable_fix)
    graph = build_graph()

    log.info("graph_invoke_start", workspace=str(path))
    final_state = graph.invoke(state, config={"recursion_limit": 30})
    log.info("graph_invoke_done")

    report_md = final_state.get("report_md", "")
    if report_md:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_md, encoding="utf-8")
        console.print(f"[green]✓ 报告已写入 {output}[/green]")

    findings = final_state.get("findings", [])
    confirmed = [f for f in findings if f.confirmed]
    table = Table(title=f"审查结果（确认 {len(confirmed)} / 总 {len(findings)}）")
    table.add_column("文件:行")
    table.add_column("类别")
    table.add_column("严重度")
    table.add_column("标题")
    for f in confirmed[:20]:
        table.add_row(f"{f.file}:{f.line}", f.category, f.severity, f.title)
    console.print(table)


@app.command()
def info() -> None:
    """打印当前配置（不暴露 API Key）。"""
    s = get_settings()
    table = Table(title="CodeSentinel 配置")
    table.add_column("项")
    table.add_column("值")
    table.add_row("LLM Provider", s.llm_provider)
    table.add_row("Provider 已配置", "✓" if s.is_provider_configured else "✗")
    table.add_row("最大轮次", str(s.max_review_rounds))
    table.add_row("启用自动修复", "✓" if s.enable_auto_fix else "✗")
    table.add_row("严重度阈值", s.severity_threshold)
    table.add_row("日志格式", s.log_format)
    console.print(table)


if __name__ == "__main__":
    app()
