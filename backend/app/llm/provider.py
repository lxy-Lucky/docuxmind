"""Single thin OpenAI-compatible client wrapper.

mimo (cloud, xiaomimimo) and lmstudio (local) both speak the OpenAI API,
so the only thing that differs is base_url + api_key + model name.
"""
from __future__ import annotations

import asyncio
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings


class LLMProvider:
    name: str
    model: str
    client: AsyncOpenAI

    def __init__(self, name: str, base_url: str, api_key: str, model: str) -> None:
        self.name = name
        self.model = model
        # OpenAI SDK requires a non-empty api_key string even for local servers
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key or "not-set")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kw: Any,
    ):
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto" if tools else None,
            stream=False,
            **kw,
        )

    async def health(self) -> bool:
        try:
            await asyncio.wait_for(self.client.models.list(), timeout=4.0)
            return True
        except Exception:
            return False


def _make(name: str) -> LLMProvider:
    if name == "mimo":
        return LLMProvider(
            "mimo", settings.mimo_base_url, settings.mimo_api_key, settings.mimo_model
        )
    if name == "lmstudio":
        return LLMProvider(
            "lmstudio",
            settings.lmstudio_base_url,
            settings.lmstudio_api_key,
            settings.lmstudio_model,
        )
    raise ValueError(f"unknown provider: {name}")


_current: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _current
    if _current is None or _current.name != settings.llm_provider:
        _current = _make(settings.llm_provider)
    return _current


def set_provider(name: str) -> LLMProvider:
    """Switch the in-process provider. Persists only for runtime; restart re-reads .env."""
    global _current
    if name not in ("mimo", "lmstudio"):
        raise ValueError(f"unknown provider: {name}")
    settings.llm_provider = name  # type: ignore[assignment]
    _current = _make(name)
    return _current
