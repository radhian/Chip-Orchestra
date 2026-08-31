from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import llm


def test_detect_memory_bytes_prefers_rocm_vram() -> None:
    nvidia_missing = FileNotFoundError()
    rocm_json = '{"card0": {"VRAM Total Memory (B)": "21474836480"}}'

    with patch("subprocess.run") as run_mock:
        run_mock.side_effect = [nvidia_missing, Mock(stdout=rocm_json)]

        total, device = llm._detect_memory_bytes()

    assert device == "rocm"
    assert total == 21474836480


def test_build_llm_runtime_uses_qwen_default_for_openai_compatible(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "EMPTY")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    fake_client = object()
    with patch.object(llm, "get_chat_model", return_value=fake_client) as get_chat_model_mock:
        runtime = llm.build_llm_runtime()

    assert runtime.provider == "openai"
    assert runtime.model == "Qwen3.8-27B-multimodal"
    assert runtime.client is fake_client
    get_chat_model_mock.assert_called_once_with(temperature=0, model="Qwen3.8-27B-multimodal")
