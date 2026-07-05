from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage


class ChatModel(Protocol):
    def invoke(self, input, config=None, **kwargs): ...


@dataclass
class LLMRuntime:
    provider: str
    model: str
    client: ChatModel | None

    def complete(self, *, system_prompt: str, user_prompt: str, fallback: str) -> str:
        if self.provider == "mock" or self.client is None:
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
            text = "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
        else:
            text = str(content)
        text = text.strip()
        return text or fallback


def build_llm_runtime() -> LLMRuntime:
    provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower() or "ollama"
    if provider == "google":
        model = os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            return LLMRuntime(provider="mock", model="mock-deterministic", client=None)
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            return LLMRuntime(provider="mock", model="mock-deterministic", client=None)

        client = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0)
        return LLMRuntime(provider="google", model=model, client=client)
    if provider == "ollama":
        model = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            from langchain_ollama import ChatOllama
        except ImportError:
            return LLMRuntime(provider="mock", model="mock-deterministic", client=None)

        client = ChatOllama(model=model, base_url=base_url, temperature=0)
        return LLMRuntime(provider="ollama", model=model, client=client)
    return LLMRuntime(provider="mock", model="mock-deterministic", client=None)
