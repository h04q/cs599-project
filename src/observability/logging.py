"""结构化日志：基于 structlog 输出 JSON 或人类可读格式。

每条日志都自动携带 agent / phase / span_id，便于在 LangSmith 之外
也能用 jq / grep 复盘 Agent 行为。
"""
from __future__ import annotations

import logging
import sys

import structlog

from src.config import get_settings


_configured = False


def configure_logging() -> None:
    """幂等配置：多次调用只生效一次。"""
    global _configured
    if _configured:
        return

    s = get_settings()

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, s.log_level.upper(), logging.INFO),
    )

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if s.log_format == "json":
        processors.append(structlog.processors.JSONRenderer(ensure_ascii=False))
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, s.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str = "codesentinel") -> structlog.stdlib.BoundLogger:
    configure_logging()
    return structlog.get_logger(name)
