from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import knowledge
from agents import rtl_author
from llm import LLMRuntime


def test_mock_runtime_returns_templates(tmp_path: Path) -> None:
    r = rtl_author.generate_rtl("a 32-bit register", "reg32")
    assert r.provider == "mock"
    assert "module reg32" in r.code
    assert r.compiled is True
    tb = rtl_author.generate_tb(r.code, "reg32", "reg")
    assert "$dumpfile" in tb and "reg32 dut" in tb


def test_extract_code_from_fenced_block() -> None:
    text = "here you go:\n```verilog\nmodule a; endmodule\n```\ndone"
    assert rtl_author.extract_code(text).strip() == "module a; endmodule"


def test_detect_top_prefers_last_module() -> None:
    code = "module leaf; endmodule\nmodule topmod(); leaf u(); endmodule"
    assert rtl_author.detect_top(code, "fallback") == "topmod"


def test_compile_check_detects_bad_rtl() -> None:
    # iverilog may be unavailable in CI -> skipped==pass; only assert when present.
    if rtl_author.iverilog_bin() is None:
        return
    ok, _ = rtl_author.compile_check({"broken.sv": "module broken( ; endmodule"})
    assert ok is False
    ok2, _ = rtl_author.compile_check({"good.sv": "module good; endmodule\n"})
    assert ok2 is True


def test_knowledge_examples_and_fixes_load() -> None:
    assert len(knowledge.load_examples()) >= 3
    assert knowledge.lookup_fix_hints("foo is not a valid l-value in bar")


class _FakeLLM:
    """Deterministic fake that returns a valid module then repairs on retry."""

    def __init__(self):
        self.calls = 0
        self.provider = "fake"
        self.model = "fake-1"

    def complete(self, *, system_prompt, user_prompt, fallback):
        self.calls += 1
        if "failed to compile" in user_prompt:
            return "```verilog\nmodule fixed; endmodule\n```"
        return "```verilog\nmodule gen; endmodule\n```"

    @property
    def is_mock(self):
        return False


def test_generate_rtl_with_fake_llm() -> None:
    rt = _FakeLLM()
    r = rtl_author.generate_rtl("simple design", "gen", runtime=rt)  # type: ignore[arg-type]
    assert r.provider  # not mock branch
    assert "module" in r.code
    assert rt.calls >= 1
