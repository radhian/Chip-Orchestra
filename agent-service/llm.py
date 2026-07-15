"""Central LLM / vision factory for the agent service — ported from GarudaChip.

Everything in the service gets its chat model from here, so the provider can be
switched with a single environment variable instead of editing code. The
DEFAULT for real runs is a fully-local setup: Ollama for chat (e.g. qwen3.5:9b)
with an optional local VLM for reading uploaded diagrams.

Configure via .env (see .env.example):

    LLM_PROVIDER        ollama | google | openai/glm | mock   (default: mock)
    OLLAMA_MODEL        e.g. qwen3.5:9b
    OLLAMA_BASE_URL     default http://localhost:11434
    OLLAMA_NUM_CTX      context window (Ollama defaults to 2048 otherwise!)
    OLLAMA_THINK        1 = enable the qwen3 thinking pass
    GARUDA_VISION_MODEL force a specific vision model for describe_image
    GOOGLE_API_KEY      required when LLM_PROVIDER=google

Two layers live here:

* GarudaChip-style module API — ``get_chat_model``, ``set_model``/
  ``current_model``, ``set_num_ctx``, ``list_ollama_models``,
  ``vision_model``/``model_supports_vision``/``describe_image`` and process-wide
  token accounting. The deep agents use this layer.
* The original thin ``LLMRuntime``/``build_llm_runtime`` wrapper (mock-safe
  ``complete``) kept for the deterministic stage handlers and the test suite.
"""
from __future__ import annotations

import functools
import os
import threading as _threading
from dataclasses import dataclass
from typing import Optional, Protocol

from langchain_core.callbacks import BaseCallbackHandler as _BaseCB
from langchain_core.messages import HumanMessage, SystemMessage


def get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").strip().lower() or "mock"


# --------------------------------------------------------------------------- #
# Per-run overrides (GarudaChip parity)
# --------------------------------------------------------------------------- #
# Per-run context-window override. When None, get_chat_model falls back to
# OLLAMA_NUM_CTX. Process-global; the most recent run's value wins.
_NUM_CTX_OVERRIDE: "int | None" = None


def set_num_ctx(n) -> None:
    """Set the Ollama context window (num_ctx) used by every subsequent
    get_chat_model call, overriding OLLAMA_NUM_CTX. Falsy clears the override."""
    global _NUM_CTX_OVERRIDE
    try:
        _NUM_CTX_OVERRIDE = int(n) if n else None
    except (TypeError, ValueError):
        _NUM_CTX_OVERRIDE = None


def _default_num_ctx() -> int:
    return _NUM_CTX_OVERRIDE or int(os.getenv("OLLAMA_NUM_CTX", "32768"))


# Per-run chat-model override (the task's llm_model picked in the UI). When
# None, get_chat_model falls back to OLLAMA_MODEL/.env.
_MODEL_OVERRIDE: "str | None" = None


# Below this on-disk size (bytes) an Ollama entry is a "cloud" stub, not real
# local weights: the `*:cloud` models are a few hundred bytes that proxy
# inference to Ollama's servers.
_CLOUD_STUB_MAX_BYTES = 50 * 1024 * 1024


def is_cloud_model(name: str, size: int = 0, parameter_size: str = "") -> bool:
    """True for an Ollama 'cloud' model — one that runs on Ollama's servers, NOT
    locally. Detected by the `:cloud`/`-cloud` tag in the name, or by the
    tell-tale tiny on-disk size of a cloud stub."""
    n = (name or "").lower()
    if ":cloud" in n or "-cloud" in n or n.endswith("cloud"):
        return True
    if size and 0 < size < _CLOUD_STUB_MAX_BYTES:
        return True
    return False


def set_model(name) -> None:
    """Pick the Ollama chat model used by every subsequent get_chat_model call,
    overriding OLLAMA_MODEL. Pass a falsy value to clear the override."""
    global _MODEL_OVERRIDE
    name = (name or "").strip() if isinstance(name, str) else ""
    _MODEL_OVERRIDE = name or None


def current_model() -> str:
    """The Ollama chat model in effect right now (override if set, else .env)."""
    return _MODEL_OVERRIDE or os.getenv("OLLAMA_MODEL", "glm-5.2:cloud")


def list_ollama_models() -> "list[dict]":
    """Installed Ollama models (name + size + family + cloud/vision flags) from
    the local Ollama daemon, so the UI can offer a picker. Best-effort: returns
    [] if Ollama isn't reachable."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        import json as _json
        import urllib.request

        with urllib.request.urlopen(f"{base}/api/tags", timeout=4) as r:  # noqa: S310
            data = _json.loads(r.read().decode())
    except Exception:  # noqa: BLE001 — Ollama down / not installed → empty picker
        return []
    out = []
    for m in data.get("models", []):
        det = m.get("details") or {}
        name = m.get("name", "")
        size = int(m.get("size") or 0)
        param = det.get("parameter_size", "")
        if not name:
            continue
        out.append({
            "name": name,
            "size": size,
            "family": det.get("family", ""),
            "parameter_size": param,
            "cloud": is_cloud_model(name, size, param),
        })
    # local models first (privacy-preserving default), then cloud, alphabetical
    out.sort(key=lambda x: (x["cloud"], x["name"]))
    return out


def _ollama_has_vision(name: str) -> bool:
    """Does this Ollama model report a 'vision' capability in /api/show?
    Authoritative for LOCAL models (cloud stubs under-report)."""
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    try:
        import json as _json
        import urllib.request

        req = urllib.request.Request(
            f"{base}/api/show", data=_json.dumps({"name": name}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=6) as r:  # noqa: S310
            info = _json.loads(r.read().decode())
    except Exception:  # noqa: BLE001
        return False
    if "capabilities" in info:
        return any("vision" in str(c).lower() for c in (info.get("capabilities") or []))
    fam = " ".join(str(v) for v in (info.get("details") or {}).values()).lower()
    return any(k in (name + " " + fam).lower()
               for k in ("vl", "vision", "llava", "4v", "minicpm-v", "moondream"))


def vision_model() -> "str | None":
    """The model used to READ an image — DECOUPLED from the RTL chat model, so a
    user on a text-only model (e.g. glm-5.2:cloud, which Ollama rejects images
    for) still gets TRUE vision: a local VLM reads the diagram into text, then
    the strong model builds the RTL from that text.

    Resolution order: GARUDA_VISION_MODEL env → the active chat model if IT
    reports vision → the first installed LOCAL model with a 'vision' capability
    → None. Google provider is handled separately in describe_image."""
    forced = os.getenv("GARUDA_VISION_MODEL", "").strip()
    if forced:
        return forced
    if get_provider() != "ollama":
        return None
    cur = current_model()
    if not is_cloud_model(cur) and _ollama_has_vision(cur):
        return cur
    for m in list_ollama_models():        # any installed local VLM (image step ≠ RTL model)
        if not m["cloud"] and _ollama_has_vision(m["name"]):
            return m["name"]
    return None


def model_supports_vision(name: "str | None" = None) -> bool:
    """True when an uploaded image can be UNDERSTOOD by a model (vs. only
    OCR'd). GARUDA_VISION forces on (1) / off (0)."""
    force = os.getenv("GARUDA_VISION", "").strip().lower()
    if force in ("1", "true", "yes", "on"):
        return True
    if force in ("0", "false", "no", "off"):
        return False
    if get_provider() in ("google", "gemini"):
        return True
    return vision_model() is not None


def describe_image(image_path, prompt: str = "", temperature: float = 0.1) -> str:
    """Have a vision model DESCRIBE an image (a hardware block diagram /
    schematic / datasheet figure) as structured text an RTL agent can use —
    blocks, labels, bit-widths, connections. Routes to vision_model() (a local
    VLM when the chat model can't see). Returns '' on any failure (caller falls
    back to OCR)."""
    import base64
    from pathlib import Path as _Path

    p = _Path(image_path)
    try:
        data = p.read_bytes()
    except Exception:  # noqa: BLE001
        return ""
    fmt = (p.suffix.lstrip(".").lower() or "png")
    if fmt == "jpg":
        fmt = "jpeg"
    b64 = base64.b64encode(data).decode()
    instruction = prompt or (
        "You are reading a HARDWARE block diagram / schematic for an RTL engineer. Describe it "
        "PRECISELY and STRUCTURALLY: list every block/module with its exact label; for each, the "
        "bit-widths and signal names shown; and EVERY connection between blocks (source → "
        "destination, signal name, direction, width). Note any buses, clocks, resets, and "
        "interfaces (e.g. a CPU I/F to an accelerator). Output a tidy bulleted spec, not prose. "
        "If text is unreadable, say so rather than guessing.")
    provider = get_provider()
    if provider == "ollama":
        # Native /api/chat with `images` — more robust than langchain's image_url
        # content blocks. `think:false` so a thinking model returns the answer in
        # `content`. Routed to vision_model(), which is a working local VLM when
        # the chat model can't read images.
        vm = vision_model()
        if not vm:
            return ""
        import json as _json
        import urllib.request

        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        # A MODEST context for the vision call: image tokens + a short
        # instruction + ~1k of output fit easily in 8k; a big window makes the
        # VLM's KV cache blow past a tight GPU's VRAM → Ollama HTTP 500.
        vctx = min(int(os.getenv("OLLAMA_VISION_NUM_CTX", "8192")), _default_num_ctx() or 8192)
        body = {
            "model": vm,
            "messages": [{"role": "user", "content": instruction, "images": [b64]}],
            "stream": False, "think": False,
            "options": {"temperature": temperature, "num_ctx": vctx},
        }
        try:
            req = urllib.request.Request(
                f"{base}/api/chat", data=_json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            timeout = float(os.getenv("OLLAMA_VISION_TIMEOUT", "240"))
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                resp = _json.loads(r.read().decode())
            return ((resp.get("message") or {}).get("content") or "").strip()
        except Exception:  # noqa: BLE001 — backend can't read the image → OCR fallback
            return ""
    try:
        model = get_chat_model(temperature=temperature)
        msg = HumanMessage(content=[
            {"type": "text", "text": instruction},
            {"type": "image_url", "image_url": {"url": f"data:image/{fmt};base64,{b64}"}},
        ])
        resp = model.invoke([msg])
        return (getattr(resp, "content", "") or "").strip()
    except Exception:  # noqa: BLE001 — model can't take images → OCR fallback
        return ""


def provider_label() -> str:
    """Human-readable label for the active chat model (for the UI)."""
    provider = get_provider()
    if provider == "ollama":
        m = current_model()
        return f"Ollama · {m} ({'cloud' if is_cloud_model(m) else 'local'})"
    if provider in ("google", "gemini"):
        return f"Google · {os.getenv('GOOGLE_MODEL', 'gemini-2.5-pro')}"
    return provider


# --------------------------------------------------------------------------- #
# Token accounting — every LLM call through get_chat_model() is counted here
# (llm_query, deep-agent internals alike), so each stage can report token use
# and the final report can state the total honestly.
# --------------------------------------------------------------------------- #
_TOKENS = {"in": 0, "out": 0, "calls": 0}
_TOK_LOCK = _threading.Lock()


def _count_usage(um) -> None:
    if not um:
        return
    with _TOK_LOCK:
        _TOKENS["in"] += int(um.get("input_tokens") or 0)
        _TOKENS["out"] += int(um.get("output_tokens") or 0)
        _TOKENS["calls"] += 1


class _TokenCounter(_BaseCB):
    """Minimal LangChain callback: harvests usage_metadata from every LLM result."""

    def on_llm_end(self, response, **kwargs):
        try:
            for gens in (getattr(response, "generations", None) or []):
                for g in gens:
                    msg = getattr(g, "message", None)
                    _count_usage(getattr(msg, "usage_metadata", None) or {})
        except Exception:  # noqa: BLE001
            pass


_TOKEN_CB = _TokenCounter()


def token_usage() -> dict:
    """Current process-wide token counters: {'in', 'out', 'calls'}."""
    with _TOK_LOCK:
        return dict(_TOKENS)


def count_subprocess_usage(input_tokens: int, output_tokens: int) -> None:
    """Fold in usage reported by out-of-process calls (run_python's llm() helper)."""
    _count_usage({"input_tokens": input_tokens, "output_tokens": output_tokens})


def fmt_tokens(n) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)


# --------------------------------------------------------------------------- #
# Chat-model factory (GarudaChip parity + the openai-compatible provider)
# --------------------------------------------------------------------------- #
def get_chat_model(temperature: float = 0.2, **kwargs):
    """Return a LangChain chat model for the configured provider.

    Args:
        temperature: sampling temperature.
        **kwargs: forwarded to the underlying ChatModel constructor
                  (``model=`` and ``num_ctx=`` are honoured as overrides).
    """
    provider = get_provider()

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        timeout = os.getenv("OLLAMA_TIMEOUT")
        extra = {}
        if timeout:
            # langchain-ollama forwards client kwargs; a generous timeout keeps
            # long RTL generations from being cut off.
            try:
                extra["client_kwargs"] = {"timeout": float(timeout)}
            except ValueError:
                pass
        # qwen3 is a "thinking" model: by default it streams a long internal
        # reasoning pass BEFORE any answer tokens. OLLAMA_THINK=1 enables it.
        think = os.getenv("OLLAMA_THINK", "0").strip().lower() in ("1", "true", "yes", "on")
        return ChatOllama(
            model=str(kwargs.pop("model", None) or current_model()),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=temperature,
            reasoning=think,
            callbacks=[_TOKEN_CB],        # token accounting (see token_usage())
            # --- Anti-repetition / runaway-generation guards ---
            # Small local models (esp. qwen) fall into degenerate loops where
            # they emit the SAME line(s) forever. A repeat penalty discourages
            # the cycle, and a hard num_predict cap guarantees generation STOPS
            # even if a loop slips through. Tunable via .env.
            repeat_penalty=float(os.getenv("OLLAMA_REPEAT_PENALTY", "1.18")),
            repeat_last_n=int(os.getenv("OLLAMA_REPEAT_LAST_N", "256")),
            num_predict=int(os.getenv("OLLAMA_NUM_PREDICT", "8192")),
            # Ollama caps the context at 2048 tokens by DEFAULT regardless of
            # the model's real window. That truncates the prompt and makes the
            # model return NOTHING — the empty-output bug. Raise via OLLAMA_NUM_CTX.
            num_ctx=int(kwargs.pop("num_ctx", None) or _default_num_ctx()),
            **extra,
            **kwargs,
        )

    if provider in ("google", "gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=google but GOOGLE_API_KEY is not set. "
                "Add it to your .env file or switch LLM_PROVIDER=ollama."
            )
        return ChatGoogleGenerativeAI(
            model=str(kwargs.pop("model", None) or os.getenv("GOOGLE_MODEL", "gemini-2.5-pro")),
            google_api_key=api_key,
            temperature=temperature,
            callbacks=[_TOKEN_CB],
            **kwargs,
        )

    if provider in ("openai", "glm", "zhipu", "zhipuai", "openai-compatible"):
        from langchain_openai import ChatOpenAI

        api_key = _env("OPENAI_API_KEY", "LLM_API_KEY", "ZHIPUAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"LLM_PROVIDER={provider} but OPENAI_API_KEY is not set."
            )
        base_url = _env("OPENAI_BASE_URL", "LLM_BASE_URL", "OPENAI_API_BASE")
        openai_kwargs = {
            "model": str(kwargs.pop("model", None)
                         or _env("OPENAI_MODEL", "LLM_MODEL", default="glm-4.6")),
            "api_key": api_key,
            "temperature": temperature,
            "callbacks": [_TOKEN_CB],
        }
        if base_url:
            openai_kwargs["base_url"] = base_url
        openai_kwargs.update(kwargs)
        return ChatOpenAI(**openai_kwargs)

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. Use 'ollama', 'google', 'openai'/'glm', or 'mock'."
    )


def _detect_memory_bytes() -> "tuple[int, str]":
    """(usable_bytes, device) for sizing the KV cache: GPU VRAM when CUDA is
    present, else system RAM. Best-effort; 0 if nothing detectable."""
    try:
        import subprocess
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4)
        mb = max(int(x) for x in out.stdout.split() if x.strip().isdigit())
        if mb > 0:
            return mb * 1024 * 1024, "cuda"
    except Exception:  # noqa: BLE001
        pass
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page_size), "cpu"
    except Exception:  # noqa: BLE001
        return 0, "cpu"


def recommended_ctx_limits() -> dict:
    """Size the context-window (num_ctx) choice to the host HARDWARE so a
    caller can't pick a window whose KV cache won't fit. Returns
    {device, total_gb, num_ctx_min, num_ctx_max, num_ctx_default}."""
    total, device = _detect_memory_bytes()
    kv_per_tok = int(os.getenv("OLLAMA_KV_BYTES_PER_TOKEN", str(56 * 1024)))
    reserve_gb = float(os.getenv("OLLAMA_RESERVE_GB", "6.0" if device == "cuda" else "8.0"))
    hard_max = int(os.getenv("OLLAMA_CTX_HARD_MAX", "262144"))
    step = 2048
    if total > 0:
        budget = max(0.0, total * 0.90 - reserve_gb * 1e9)
        raw = int(budget / kv_per_tok)
        num_ctx_max = max(4096, min(hard_max, (raw // step) * step))
    else:
        num_ctx_max = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
    num_ctx_default = min(num_ctx_max, _default_num_ctx())
    return {
        "device": device,
        "total_gb": round(total / 1e9, 1) if total else 0.0,
        "num_ctx_min": 2048,
        "num_ctx_max": int(num_ctx_max),
        "num_ctx_step": step,
        "num_ctx_default": int(num_ctx_default),
    }


# --------------------------------------------------------------------------- #
# Thin, fallback-safe completion wrapper (original agent-service contract)
# --------------------------------------------------------------------------- #
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


def build_llm_runtime(model_override: Optional[str] = None) -> LLMRuntime:
    """Build the configured LLM runtime.

    ``model_override`` (e.g. a per-task model chosen in the UI) takes
    precedence over the env-configured model for the active provider. Falls
    back to the deterministic mock when the provider SDK / credentials are
    unavailable so the stack still runs end-to-end without any API key.
    """
    provider = get_provider()
    model_override = (model_override or "").strip() or None

    if provider == "mock":
        return _mock()

    if provider == "ollama":
        model = model_override or current_model()
    elif provider in ("google", "gemini"):
        model = model_override or _env("GOOGLE_MODEL", default="gemini-2.5-pro")
    else:
        model = model_override or _env("OPENAI_MODEL", "LLM_MODEL", default="glm-4.6")

    try:
        client = get_chat_model(temperature=0, model=model)
    except Exception:  # noqa: BLE001 - missing SDK/credentials → mock fallback
        return _mock()
    canonical = "openai" if provider in ("glm", "zhipu", "zhipuai", "openai-compatible") else provider
    return LLMRuntime(provider=canonical, model=model, client=client)


__all__ = [
    "ChatModel",
    "LLMRuntime",
    "build_llm_runtime",
    "get_chat_model",
    "get_provider",
    "provider_label",
    "set_model",
    "current_model",
    "set_num_ctx",
    "list_ollama_models",
    "is_cloud_model",
    "vision_model",
    "model_supports_vision",
    "describe_image",
    "token_usage",
    "count_subprocess_usage",
    "fmt_tokens",
    "recommended_ctx_limits",
]
