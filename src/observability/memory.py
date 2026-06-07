"""跨会话长期记忆：把每次审查发现的"模式 → 修复策略"存入 SQLite。

设计意图：
- 同一类 Bug 第二次出现时，Agent 能从历史记忆里召回之前接受的修复方案，
  减少 LLM 重复劳动并提升修复一致性。
- 简单 schema，避免引入向量数据库的初装成本；后续若要做语义召回可平滑
  迁移到 FAISS / Chroma。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


DEFAULT_DB = Path(".codesentinel/memory.sqlite3")


@dataclass(slots=True)
class MemoryRecord:
    pattern: str        # 形如 "py:eval-on-user-input"
    description: str    # 自然语言简述
    fix_strategy: str   # 修复思路
    severity: str
    accepted: bool
    created_at: str


class MemoryStore:
    """轻量 SQLite 包装，支持按 pattern 查询历史经验。"""

    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS review_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT NOT NULL,
                    description TEXT NOT NULL,
                    fix_strategy TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    accepted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_pattern ON review_memory(pattern)"
            )

    def remember(self, record: MemoryRecord) -> int:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO review_memory
                    (pattern, description, fix_strategy, severity, accepted, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.pattern,
                    record.description,
                    record.fix_strategy,
                    record.severity,
                    int(record.accepted),
                    record.created_at or datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cur.lastrowid)

    def recall(self, pattern: str, limit: int = 5) -> list[MemoryRecord]:
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT pattern, description, fix_strategy, severity, accepted, created_at
                FROM review_memory
                WHERE pattern = ? AND accepted = 1
                ORDER BY id DESC LIMIT ?
                """,
                (pattern, limit),
            ).fetchall()
        return [
            MemoryRecord(
                pattern=r["pattern"],
                description=r["description"],
                fix_strategy=r["fix_strategy"],
                severity=r["severity"],
                accepted=bool(r["accepted"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def export_all(self) -> str:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM review_memory").fetchall()
        return json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2)
