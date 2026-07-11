"""LLM runtime construction and a thin, fallback-safe completion wrapper.

Supported providers (selected via ``LLM_PROVIDER``):

* ``openai`` / ``glm`` / ``zhipu`` - any OpenAI-compatible chat endpoint. Used
  for ZhipuAI GLM (e.g. ``glm-4.6`` / GLM-5.2) by pointing ``OPENAI_BASE_URL``
  at the vendor gateway. Reads ``OPENAI_API_KEY`` + ``OPENAI_MODEL``.
* ``ollama`` - local Ollama server (``OLLAMA_BASE_URL`` + ``OLLAMA_MODEL``).
* ``google`` - Gemini via ``langchain-google-genai``.
* ``mock`` - deterministic stub, no network. Also the automatic fallback when a
  provider is selected but its SDK/credentials are unavailable, so the stack
  still runs end-to-end locally without any API key.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Protocol

from langchain_core.messages import HumanMessage, SystemMessage


class ChatModel(Protocol):
    def invoke(self, input, config=None, **kwargs): ...


@dataclass
class LLMRuntime:
    provider: str
    model: str
    client: Optional[ChatModel]

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock" or self.client is None

    def complete(self, *, system_prompt: str, user_prompt: str, fallback: str) -> str:
        """Return the model completion, or ``fallback`` on mock/error/empty."""
        if self.is_mock:
            return fallback
        try:
            response = self.client.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
        except Exception:
            return fallback
        content = getattr(response, "content", response)
        if isinstance(content, list):
            text = "\n".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        else:
            text = str(content)
        text = text.strip()
        return text or fallback


def _mock() -> LLMRuntime:
    return LLMRuntime(provider="mock", model="mock-deterministic", client=None)


def _env(*names: str, default: str = "") -> str:
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return val
    return default


def build_llm_runtime() -> LLMRuntime:
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"

    if provider in ("openai", "glm", "zhipu", "zhipuai", "openai-compatible"):
        api_key = _env("OPENAI_API_KEY", "LLM_API_KEY", "ZHIPUAI_API_KEY")
        base_url = _env("OPENAI_BASE_URL", "LLM_BASE_URL", "OPENAI_API_BASE")
        model = _env("OPENAI_MODEL", "LLM_MODEL", default="glm-4.6")
        if not api_key:
            return _mock()
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            return _mock()
        kwargs = {"model": model, "api_key": api_key, "temperature": 0}
        if base_url:
            kwargs["base_url"] = base_url
        try:
            client = ChatOpenAI(**kwargs)
        except Exception:
            return _mock()
        return LLMRuntime(provider="openai", model=model, client=client)

    if provider == "google":
        model = _env("GOOGLE_MODEL", default="gemini-2.5-pro")
        api_key = _env("GOOGLE_API_KEY")
        if not api_key:
            return _mock()
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            return _mock()
        try:
            client = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)
        except Exception:
            return _mock()
        return LLMRuntime(provider="google", model=model, client=client)

    if provider == "ollama":
        model = _env("OLLAMA_MODEL", default="qwen2.5-coder:7b")
        base_url = _env("OLLAMA_BASE_URL", default="http://localhost:11434")
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            return _mock()
        try:
            client = ChatOllama(model=model, base_url=base_url, temperature=0)
        except Exception:
            return _mock()
        return LLMRuntime(provider="ollama", model=model, client=client)

    return _mock()


__all__ = ["ChatModel", "LLMRuntime", "build_llm_runtime"]
