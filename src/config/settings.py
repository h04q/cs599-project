"""Settings：从环境变量加载所有配置。"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


Provider = Literal["deepseek", "anthropic", "openai", "qwen", "ollama"]
Severity = Literal["low", "medium", "high"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- LLM 总开关 ----
    llm_provider: Provider = "deepseek"

    # ---- DeepSeek ----
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # ---- Anthropic ----
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # ---- OpenAI ----
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    # ---- Qwen / DashScope OpenAI-compatible API ----
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    # ---- Ollama 本地兜底 ----
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"

    # ---- Agent 行为 ----
    max_review_rounds: int = Field(default=2, ge=1, le=5)
    enable_auto_fix: bool = True
    severity_threshold: Severity = "medium"

    # ---- 可观测性 ----
    langsmith_api_key: str = ""
    langsmith_project: str = "cs599-codesentinel"
    langsmith_tracing: bool = False

    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    # ---- 内部派生 ----
    @property
    def is_provider_configured(self) -> bool:
        match self.llm_provider:
            case "deepseek":
                return bool(self.deepseek_api_key)
            case "anthropic":
                return bool(self.anthropic_api_key)
            case "openai":
                return bool(self.openai_api_key)
            case "qwen":
                return bool(self.qwen_api_key)
            case "ollama":
                return True  # 本地无需 key
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
