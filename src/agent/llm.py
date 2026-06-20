"""
src/agent/llm.py
================
Ultra-thin LLM client. ONE class, ONE method.

Designed to point at any OpenAI-compatible endpoint (OpenAI, DeepSeek, Qwen,
Moonshot, Zhipu, local vLLM, ...) via OPENAI_BASE_URL.

We do not use a framework here on purpose: you should be able to see exactly
which HTTP request is being made on every loop step.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass
class LLMResponse:
    """Normalized response shape used by the loop."""
    content: str | None
    tool_calls: list[dict[str, Any]]
    raw: Any                # the original SDK response, kept for trajectory store
    usage: dict[str, int]   # {"prompt_tokens": ..., "completion_tokens": ...}


class LLMClient:
    """A tiny wrapper around the OpenAI SDK so callers don't see provider details."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("AGENT_MODEL", "gpt-4o-mini")
        self._client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls: list[dict[str, Any]] = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,  # JSON string
                })

        usage = {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
        }

        return LLMResponse(
            content=msg.content,
            tool_calls=tool_calls,
            raw=resp,
            usage=usage,
        )
