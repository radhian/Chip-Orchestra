from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.deep_agent import make_python_tools

def test_run_python_injects_correct_llm_helper_for_openai_compatible(tmp_path) -> None:
    # Set up environment for OpenAI-compatible provider
    env_vars = {
        "LLM_PROVIDER": "openai-compatible",
        "OPENAI_BASE_URL": "http://172.16.100.2:10000/v1",
        "OPENAI_MODEL": "Qwen3.8-27B-multimodal",
        "OPENAI_API_KEY": "test-key"
    }
    
    with patch.dict(os.environ, env_vars), patch("subprocess.run") as run_mock:
        # Create tools
        tools = make_python_tools(tmp_path)
        run_python = next(t for t in tools if t.name == "run_python")
        
        # Test code that uses the llm() helper
        code = "print(llm('hello'))"
        
        # We mock the subprocess.run call which executes the script
        run_mock.return_value = Mock(returncode=0, stdout="Mocked Output", stderr="")
        
        # Invoke the tool
        run_python.invoke({"code": code})
        
        # Check that the script file was written with the correct LLM helper
        script_path = tmp_path / "work" / "_snippet.py"
        assert script_path.exists()
        script_content = script_path.read_text()
        
        # Verify the OpenAI-compatible logic is in the injected helper
        assert "if _p in ('openai', 'glm', 'openai-compatible', 'zhipu', 'zhipuai'):" in script_content
        assert "http://172.16.100.2:10000/v1" in script_content
        assert "Authorization': f'Bearer {_k}'" in script_content
        assert "/chat/completions" in script_content
        
        # Verify environment variables passed to the subprocess
        called_env = run_mock.call_args[1]["env"]
        assert called_env["GARUDA_LLM_PROVIDER"] == "openai-compatible"
        assert called_env["GARUDA_LLM_BASE_URL"] == "http://172.16.100.2:10000/v1"
        assert called_env["GARUDA_LLM_API_KEY"] == "test-key"
        assert called_env["GARUDA_LLM_MODEL"] == "Qwen3.8-27B-multimodal"

def test_run_python_injects_correct_llm_helper_for_ollama(tmp_path) -> None:
    # Set up environment for Ollama provider
    env_vars = {
        "LLM_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://ollama-host:11434",
        "OLLAMA_MODEL": "qwen3.5:9b"
    }
    
    with patch.dict(os.environ, env_vars), patch("subprocess.run") as run_mock:
        tools = make_python_tools(tmp_path)
        run_python = next(t for t in tools if t.name == "run_python")
        
        run_mock.return_value = Mock(returncode=0, stdout="Mocked Output", stderr="")
        run_python.invoke({"code": "print(llm('hello'))"})
        
        script_path = tmp_path / "work" / "_snippet.py"
        script_content = script_path.read_text()
        
        # Verify Ollama fallback logic is present
        assert "OLLAMA_BASE_URL', 'http://localhost:11434'" in script_content
        assert "/api/chat" in script_content
        
        called_env = run_mock.call_args[1]["env"]
        assert called_env["GARUDA_LLM_PROVIDER"] == "ollama"
        assert called_env["GARUDA_LLM_MODEL"] == "qwen3.5:9b"
