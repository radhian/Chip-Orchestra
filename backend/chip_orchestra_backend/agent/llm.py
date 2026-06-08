"""LLM provider + text-wrangling helpers.

Mirrors GarudaChip's approach: a local Ollama chat model by default, with an
optional Google Gemini fallback, plus small utilities to pull code/JSON back
out of the model's markdown responses.
"""

from __future__ import annotations

import json
import re

from .. import control
from ..config import get_settings


class LLMUnavailable(RuntimeError):
    """Raised when no usable LLM backend can be constructed."""


def build_llm(model: str | None = None, temperature: float | None = None):
    """Construct a LangChain chat model for the configured provider."""
    settings = get_settings()
    temp = settings.llm_temperature if temperature is None else temperature
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as exc:  # pragma: no cover
            raise LLMUnavailable(
                "LLM_PROVIDER=gemini but langchain-google-genai is not installed "
                "(install the `gemini` extra)."
            ) from exc
        if not settings.google_api_key:
            raise LLMUnavailable("LLM_PROVIDER=gemini requires GOOGLE_API_KEY.")
        return ChatGoogleGenerativeAI(
            model=model or settings.gemini_model,
            temperature=temp,
            google_api_key=settings.google_api_key,
        )

    # Default: local Ollama.
    try:
        from langchain_ollama import ChatOllama
    except ImportError as exc:  # pragma: no cover
        raise LLMUnavailable("langchain-ollama is not installed.") from exc
    return ChatOllama(
        model=model or settings.ollama_model,
        base_url=settings.ollama_host,
        temperature=temp,
        num_ctx=settings.ollama_num_ctx,
        num_predict=settings.ollama_num_predict,
    )


def _content(message) -> str:
    text = getattr(message, "content", message)
    if isinstance(text, list):  # some providers return content parts
        text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in text)
    return str(text)


def complete(
    prompt: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    task_id: str | None = None,
) -> str:
    """Completion returning the model's text.

    When ``task_id`` is given the response is **streamed** and a stop/cancel
    request is checked between chunks, so a long generation can be interrupted
    within ~a token instead of running to completion.
    """
    settings = get_settings()
    if settings.llm_provider.lower() == "ollama" and not settings.ollama_think:
        # Qwen3 soft-switch: skip the long <think> reasoning for interactive speed.
        prompt = f"{prompt}\n/no_think"
    llm = build_llm(model=model, temperature=temperature)

    if task_id is None:
        return _content(llm.invoke(prompt))

    parts: list[str] = []
    for i, chunk in enumerate(llm.stream(prompt)):
        parts.append(_content(chunk))
        if i % 4 == 0:
            control.checkpoint(task_id)  # raises PipelineStopped/Cancelled if requested
    control.checkpoint(task_id)
    return "".join(parts)


# --- response parsing -------------------------------------------------------
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_OPEN_RE = re.compile(r"```[a-zA-Z0-9_+\-]*[ \t]*\r?\n")
_FENCE_CLOSE_RE = re.compile(r"\r?\n[ \t]*```")


def strip_reasoning(text: str) -> str:
    """Drop <think>...</think> reasoning emitted by models like qwen3.5.

    Qwen3 emits ``<think>reasoning</think>answer``; keep only the answer. Also
    tolerate well-formed blocks elsewhere and dangling unclosed think tags.
    """
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    else:
        text = _THINK_RE.sub("", text)
        if "<think>" in text:  # unclosed reasoning, nothing usable after it
            text = text.split("<think>", 1)[0]
    return text.strip()


def extract_code_block(text: str, lang: str = "verilog") -> str:  # noqa: ARG001
    """Pull code out of a model response, robust to unclosed/missing fences."""
    text = strip_reasoning(text)
    opener = _FENCE_OPEN_RE.search(text)
    if opener:
        rest = text[opener.end() :]
        closer = _FENCE_CLOSE_RE.search(rest)
        return (rest[: closer.start()] if closer else rest).strip()
    # No fenced block: strip any stray leading ```lang / trailing ``` and return.
    cleaned = re.sub(r"^```[a-zA-Z0-9_+\-]*[ \t]*\r?\n?", "", text)
    cleaned = re.sub(r"\r?\n?[ \t]*```\s*$", "", cleaned)
    return cleaned.strip()


def guess_tb_module(verilog: str, fallback: str = "tb") -> str:
    """Find the testbench's top module name (prefer tb/test/bench-named ones)."""
    names = find_module_names(verilog)
    for name in names:
        low = name.lower()
        if "tb" in low or "test" in low or "bench" in low:
            return name
    return names[-1] if names else fallback


_MODULE_BLOCK_RE = re.compile(r"(?:^|\n)[ \t]*module\s+(\w+).*?endmodule", re.DOTALL | re.IGNORECASE)


def split_verilog_modules(code: str) -> dict[str, str]:
    """Deterministically split combined Verilog into one file per module.

    Returns ``{ "<module>.v": code }``. Shared preprocessor/comment preamble
    (``\\`timescale``, ``\\`define``, ``\\`include``, comments) is duplicated into
    each file so every module is independently compilable. Returns ``{}`` when the
    code has zero or one module (caller should keep it as a single file).
    """
    blocks = list(_MODULE_BLOCK_RE.finditer(code))
    if len(blocks) <= 1:
        return {}

    preamble = code[: blocks[0].start()]
    safe_pre = "\n".join(
        line for line in preamble.splitlines()
        if line.strip().startswith(("`", "//", "/*", "*"))
    ).strip()

    files: dict[str, str] = {}
    for block in blocks:
        name = block.group(1)
        body = block.group(0).strip()
        content = f"{safe_pre}\n\n{body}\n" if safe_pre else f"{body}\n"
        fname = f"{name}.v"
        # Avoid clobbering if two modules share a name (rare) — suffix the dupe.
        if fname in files:
            fname = f"{name}_{len(files)}.v"
        files[fname] = content
    return files


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction from a possibly chatty response."""
    text = strip_reasoning(text)
    match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    candidate = match.group(1) if match else text
    # Fall back to the outermost {...} span.
    if not match:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end != -1:
            candidate = candidate[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}


_MODULE_RE = re.compile(r"\bmodule\s+(\w+)", re.IGNORECASE)


def find_module_names(verilog: str) -> list[str]:
    return _MODULE_RE.findall(verilog)


def guess_top_module(verilog: str, fallback: str = "top") -> str:
    names = find_module_names(verilog)
    # The top module is most often the last one defined.
    return names[-1] if names else fallback
