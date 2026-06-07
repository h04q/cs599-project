"""LLM 输出 JSON 提取的健壮性测试。"""
from __future__ import annotations

from src.agent.llm_helpers import _extract_json


def test_extract_json_from_fenced_block():
    text = "好的：\n```json\n[{\"a\": 1}]\n```\n完毕"
    assert _extract_json(text, "test") == [{"a": 1}]


def test_extract_json_with_surrounding_text():
    text = '前置噪声...{"x": 2, "y": [1,2,3]}尾部噪声'
    assert _extract_json(text, "test") == {"x": 2, "y": [1, 2, 3]}


def test_extract_json_returns_none_on_unparsable():
    assert _extract_json("纯自然语言无 json", "test") is None
    assert _extract_json("", "test") is None
