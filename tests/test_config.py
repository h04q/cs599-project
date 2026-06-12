"""配置模块测试：确保环境变量正确解析、默认值合理。"""
from __future__ import annotations

import importlib

import pytest

import src.config.settings as settings_mod


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings_mod.get_settings.cache_clear()
    s = settings_mod.Settings(_env_file=None)
    assert s.llm_provider == "deepseek"
    assert s.max_review_rounds == 2
    assert s.is_provider_configured is False  # 未填 key


def test_settings_provider_switch(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    settings_mod.get_settings.cache_clear()
    s = settings_mod.Settings(_env_file=None)
    assert s.llm_provider == "ollama"
    # ollama 本地无需 key
    assert s.is_provider_configured is True


def test_settings_qwen_provider_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    settings_mod.get_settings.cache_clear()
    s = settings_mod.Settings(_env_file=None)
    assert s.qwen_model == "qwen-plus"
    assert s.qwen_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert s.is_provider_configured is False

    monkeypatch.setenv("QWEN_API_KEY", "sk-test")
    s = settings_mod.Settings(_env_file=None)
    assert s.is_provider_configured is True


def test_settings_invalid_provider_falls_back(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-vendor")
    settings_mod.get_settings.cache_clear()
    with pytest.raises(Exception):
        # pydantic 会拒绝非法 Literal
        settings_mod.Settings(_env_file=None)
