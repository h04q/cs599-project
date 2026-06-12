"""LLM 客户端工厂。

把 provider 切换收敛到一处：上层 Agent 永远拿到一个 LangChain 兼容的
ChatModel，无需关心后端是 DeepSeek 还是 Anthropic。
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from .settings import Settings, get_settings


class LLMConfigError(RuntimeError):
    """配置缺失时抛出，避免运行到一半才发现 Key 没填。"""


def build_llm(settings: Settings | None = None, **overrides: Any) -> BaseChatModel:
    """根据 settings.llm_provider 构造 ChatModel 实例。

    Args:
        settings: 可注入测试 Settings；默认走单例。
        overrides: temperature / max_tokens 等运行时覆盖项。

    Returns:
        LangChain ChatModel 实例。
    """
    s = settings or get_settings()

    if not s.is_provider_configured:
        raise LLMConfigError(
            f"LLM provider {s.llm_provider!r} 未正确配置 — 请检查 .env 中的 API Key。"
        )

    temperature = overrides.pop("temperature", 0.1)

    if s.llm_provider == "deepseek":
        # DeepSeek 走 OpenAI 兼容协议
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=s.deepseek_model,
            api_key=s.deepseek_api_key,
            base_url=s.deepseek_base_url,
            temperature=temperature,
            **overrides,
        )

    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {}
        if s.openai_base_url:
            kwargs["base_url"] = s.openai_base_url

        return ChatOpenAI(
            model=s.openai_model,
            api_key=s.openai_api_key,
            temperature=temperature,
            **kwargs,
            **overrides,
        )

    if s.llm_provider == "qwen":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=s.qwen_model,
            api_key=s.qwen_api_key,
            base_url=s.qwen_base_url,
            temperature=temperature,
            **overrides,
        )

    if s.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=s.anthropic_model,
            api_key=s.anthropic_api_key,
            temperature=temperature,
            **overrides,
        )

    if s.llm_provider == "ollama":
        # Ollama 通过 OpenAI 兼容端点（/v1）调用，避免再引入新依赖
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=s.ollama_model,
            api_key="ollama",  # 占位符，本地无需鉴权
            base_url=f"{s.ollama_base_url}/v1",
            temperature=temperature,
            **overrides,
        )

    raise LLMConfigError(f"未知 LLM provider: {s.llm_provider}")
