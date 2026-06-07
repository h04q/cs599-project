"""配置模块：环境变量加载 + LLM provider 路由。

设计要点：
- 严格走 .env / 环境变量，不允许在代码里硬编码 Key（学术纪律要求）。
- 通过 pydantic-settings 提供类型安全的 Settings 单例。
- LLM 客户端工厂统一封装，便于在 deepseek / anthropic / ollama 之间切换。
"""

from .settings import Settings, get_settings
from .llm import build_llm

__all__ = ["Settings", "get_settings", "build_llm"]
