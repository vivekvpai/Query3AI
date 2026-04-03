"""
Unified LLM dispatch client for Query3AI.

Centralizes all LiteLLM calls so that API key resolution, base URL routing,
and model selection happen in exactly one place instead of being duplicated
across decision_service, reasoning_service, toc_service, verification_service,
and tree_service.
"""
from __future__ import annotations

from typing import Literal

import litellm  # type: ignore

litellm.suppress_debug_info = True

from query3ai.config.settings import settings  # type: ignore

# Agent name → (model getter, api_key getter, api_base getter)
_AGENT_CONFIG = {
    "tree": (
        settings.get_active_tree_model,
        settings.get_tree_api_key,
        settings.get_tree_api_base,
    ),
    "decision": (
        settings.get_active_decision_model,
        settings.get_decision_api_key,
        settings.get_decision_api_base,
    ),
    "reasoning": (
        settings.get_active_reasoning_model,
        settings.get_reasoning_api_key,
        settings.get_reasoning_api_base,
    ),
}

AgentName = Literal["tree", "decision", "reasoning"]


def call_llm(
    agent: AgentName,
    messages: list[dict],
    temperature: float | None = None,
    response_format: dict | None = None,
) -> str:
    """
    Dispatch an LLM completion request for the given agent role.

    Args:
        agent: Which agent's model/key/base configuration to use.
        messages: The chat-format message list.
        temperature: Optional temperature override. Omitted → provider default.
        response_format: Optional structured output format (e.g. {"type": "json_object"}).

    Returns:
        The raw text content from the model response (stripped).
    """
    model_fn, key_fn, base_fn = _AGENT_CONFIG[agent]

    kwargs: dict = {}
    api_key = key_fn()
    if api_key:
        kwargs["api_key"] = api_key
    api_base = base_fn()
    if api_base:
        kwargs["api_base"] = api_base
    if temperature is not None:
        kwargs["temperature"] = temperature
    if response_format is not None:
        kwargs["response_format"] = response_format

    response = litellm.completion(
        model=model_fn(),
        messages=messages,
        **kwargs,
    )
    return (response.choices[0].message.content or "").strip()
