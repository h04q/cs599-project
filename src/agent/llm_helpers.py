"""所有 Agent 节点共享的 LLM 调用辅助 + JSON 输出兜底解析。"""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.config import build_llm
from src.observability import get_logger


_log = get_logger("agent.llm")
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.S)


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    *,
    agent_name: str,
    temperature: float = 0.1,
) -> Any:
    """单轮 LLM 调用，期望 JSON 输出；解析失败返回 None。

    Reviewer/Verifier 等节点不依赖 Function Calling 中的 tool 循环，仅做
    "读上下文 → 输出结构化结论"，用这个简化路径更稳定。
    """
    llm = build_llm(temperature=temperature)
    msgs = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    _log.info("llm_call", agent=agent_name, prompt_chars=len(user_prompt))
    resp = llm.invoke(msgs)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return _extract_json(text, agent_name)


def _extract_json(text: str, agent_name: str) -> Any:
    """容忍 ```json fenced``` / 前后多余文本 / 单个 dict / list。"""
    if not text:
        return None
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else text.strip()
    # 再尝试抓首个 [ ... ] / { ... }
    if not (candidate.startswith("[") or candidate.startswith("{")):
        for opener, closer in (("{", "}"), ("[", "]")):
            i = candidate.find(opener)
            j = candidate.rfind(closer)
            if 0 <= i < j:
                candidate = candidate[i : j + 1]
                break
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        _log.warning(
            "llm_json_parse_failed",
            agent=agent_name,
            error=str(e),
            sample=text[:200],
        )
        return None
