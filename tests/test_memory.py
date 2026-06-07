"""SQLite 长期记忆：写入 / 召回 / 序列化的端到端测试。"""
from __future__ import annotations

from pathlib import Path

from src.observability.memory import MemoryRecord, MemoryStore


def test_remember_and_recall_only_accepted(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "m.sqlite3")
    store.remember(MemoryRecord(
        pattern="security:hardcoded-key", description="d1",
        fix_strategy="使用环境变量", severity="high",
        accepted=True, created_at="",
    ))
    store.remember(MemoryRecord(
        pattern="security:hardcoded-key", description="d2",
        fix_strategy="不要这么改", severity="high",
        accepted=False, created_at="",
    ))
    found = store.recall("security:hardcoded-key")
    assert len(found) == 1
    assert "环境变量" in found[0].fix_strategy


def test_recall_unknown_pattern(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "m.sqlite3")
    assert store.recall("unknown:pattern") == []
