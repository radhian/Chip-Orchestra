"""Write-time contracts the deep agents' file tool enforces.

These are the gates that keep the generated design in the shape the rest of the
flow assumes — a plain Verilog-2001 multi-file design — rather than relying on
the model to remember the rules.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.deep_agent import _is_provider_failure, make_fs_tools
from agents.stage_handlers import _assert_contract_satisfied


def _write_tool(base: Path):
    tools = {t.name: t for t in make_fs_tools(base)}
    return tools["write_file_disk"]


def test_systemverilog_under_rtl_is_rejected(tmp_path: Path) -> None:
    write = _write_tool(tmp_path)

    result = write.invoke({"path": "rtl/alu.sv", "content": "module alu; endmodule\n"})

    assert "REJECTED" in result
    assert "rtl/alu.v" in result
    assert not (tmp_path / "rtl" / "alu.sv").exists(), "the .sv must not be written at all"


def test_systemverilog_testbench_is_rejected(tmp_path: Path) -> None:
    write = _write_tool(tmp_path)

    result = write.invoke({"path": "tb/alu_tb.sv", "content": "module alu_tb; endmodule\n"})

    assert "REJECTED" in result
    assert "tb/alu_tb.v" in result


def test_svh_header_is_redirected_to_vh(tmp_path: Path) -> None:
    write = _write_tool(tmp_path)

    result = write.invoke({"path": "rtl/params.svh", "content": "`define W 8\n"})

    assert "rtl/params.vh" in result


def test_plain_verilog_is_written(tmp_path: Path) -> None:
    write = _write_tool(tmp_path)

    result = write.invoke({"path": "rtl/alu.v", "content": "module alu; endmodule\n"})

    assert "REJECTED" not in result
    assert (tmp_path / "rtl" / "alu.v").is_file()


def test_python_golden_model_is_unaffected_by_the_verilog_contract(tmp_path: Path) -> None:
    # The contract is about rtl/ and tb/ only — GOLDEN_GEN writes Python freely.
    write = _write_tool(tmp_path)

    result = write.invoke({"path": "golden/model/alu.py", "content": "def alu(a, b):\n    return a + b\n"})

    assert "REJECTED" not in result
    assert (tmp_path / "golden" / "model" / "alu.py").is_file()


# --------------------------------------------------------------------------- #
# Provider failures are not agent mistakes. An out-of-credit / unauthorized /
# unreachable provider means NO work happened, so it must abort the stage rather
# than return an empty result the flow then treats as a finished golden model.
# --------------------------------------------------------------------------- #
def test_out_of_credit_is_classified_as_a_provider_failure() -> None:
    # The real message that reached the approval gate as "0/0 tests passing".
    exc = RuntimeError(
        "this model uses extra usage only (not included plan usage) and your extra "
        "usage balance is empty, add extra usage or turn on auto reload at "
        "https://ollama.com/settings (status code: 402)"
    )

    assert _is_provider_failure(exc)


def test_auth_quota_and_connection_failures_are_provider_failures() -> None:
    for message in (
        "Error code: 401 - invalid api key",
        "openai.RateLimitError: status code: 429",
        "insufficient_quota: You exceeded your current quota",
        "HTTPConnectionPool: Max retries exceeded (connection refused)",
        'model "qwen3.5:9b" not found, try pulling it first',
    ):
        assert _is_provider_failure(RuntimeError(message)), message


def test_an_ordinary_agent_error_is_not_a_provider_failure() -> None:
    # A bad tool call or a model that wrote nonsense is recoverable by the
    # stage's own repair passes — it must NOT be escalated to a hard stage fail.
    for message in (
        "KeyError: 'ports'",
        "recursion limit of 90 reached",
        "ValueError: could not convert string to float",
    ):
        assert not _is_provider_failure(RuntimeError(message)), message


# --------------------------------------------------------------------------- #
# The approved golden contract binds RTL_GEN. A run that reaches the human gate
# as "6 IP blocks" must not ship as one stub named after the task.
# --------------------------------------------------------------------------- #
class _Ctx:
    """Minimal StageContext stand-in for the contract assertion."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace


def _contract_workspace(tmp_path: Path, ips) -> Path:
    (tmp_path / "golden").mkdir(parents=True, exist_ok=True)
    (tmp_path / "golden" / "golden_summary.json").write_text(
        json.dumps({"top": "sobel_top", "ips": [{"name": n, "tier": t} for n, t in ips]})
    )
    return tmp_path


def test_partial_rtl_against_a_golden_contract_fails_the_stage(tmp_path: Path) -> None:
    ws = _contract_workspace(tmp_path, [("pe", "ip"), ("cgra_array", "subtop"),
                                        ("sobel_top", "top")])
    status = {"files": ["nano_cgra_3x3_for_sobel_filter_accelerator.v"]}
    struct = ["the golden contract defines these IP blocks but no RTL module implements "
              "them — write rtl/<name>.v for each: pe, cgra_array"]

    with pytest.raises(RuntimeError) as excinfo:
        _assert_contract_satisfied(_Ctx(ws), status, miss=[], struct=struct)

    assert "did not satisfy the approved golden contract" in str(excinfo.value)
    assert "pe" in str(excinfo.value)


def test_unwritten_planned_files_fail_the_stage(tmp_path: Path) -> None:
    ws = _contract_workspace(tmp_path, [("pe", "ip"), ("sobel_top", "top")])

    with pytest.raises(RuntimeError) as excinfo:
        _assert_contract_satisfied(_Ctx(ws), {"files": ["sobel_top.v"]},
                                   miss=["pe.v"], struct=[])

    assert "pe.v" in str(excinfo.value)


def test_a_satisfied_contract_passes(tmp_path: Path) -> None:
    ws = _contract_workspace(tmp_path, [("pe", "ip"), ("sobel_top", "top")])

    _assert_contract_satisfied(_Ctx(ws), {"files": ["pe.v", "sobel_top.v"]},
                               miss=[], struct=[])


def test_a_run_without_a_golden_contract_is_not_gated(tmp_path: Path) -> None:
    # No GOLDEN_GEN (no provider, or a pre-GOLDEN_GEN task): keep the old
    # best-effort behaviour rather than failing every legacy run.
    _assert_contract_satisfied(_Ctx(tmp_path), {"files": ["design.v"]},
                               miss=["pe.v"], struct=["the whole design is ONE file."])
