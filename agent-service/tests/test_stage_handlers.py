from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.stage_handlers import StageContext, dispatch


def _ctx(tmp_path: Path, stage: str, **kwargs) -> StageContext:
    workspace = tmp_path
    for sub in ("rtl", "tb", "reports", "waves", "gds", "spec", "plans", "exports"):
        (workspace / sub).mkdir(parents=True, exist_ok=True)
    return StageContext(task_id="task-42", stage=stage, workspace=workspace, **kwargs)


def test_spec_ingest_writes_structured_spec(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "SPEC_INGEST", prompt="Build a 32-bit register", context={"task_name": "reg32"})
    result = dispatch(sc)

    assert result.agent_name == "SpecInterpreter"
    assert "spec/spec.json" in result.workspace_files
    spec = json.loads((tmp_path / "spec/spec.json").read_text())
    assert spec["task_id"] == "task-42"
    assert result.structured_conclusion["top_module"]


def test_rtl_gen_writes_top_module(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "RTL_GEN", context={"top_module": "alu"})
    result = dispatch(sc)

    assert result.agent_name == "RTLAuthor"
    assert (tmp_path / "rtl/alu.sv").is_file()
    assert (tmp_path / "reports/rtl_architecture.md").is_file()


def test_tb_gen_writes_self_checking_testbench(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "TB_GEN", context={"top_module": "alu"})
    result = dispatch(sc)

    assert result.agent_name == "Verifier"
    tb = (tmp_path / "tb/alu_tb.sv").read_text()
    assert "$dumpfile" in tb
    assert "alu dut" in tb


def test_signoff_reads_eda_reports(tmp_path: Path) -> None:
    report = {
        "stage": "DRC_LVS",
        "metrics": {"wns_ns": 0.12},
        "signoff": {"failed": []},
        "tapeout_ready": True,
    }
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "reports/drc_lvs_report.json").write_text(json.dumps(report))

    sc = _ctx(tmp_path, "SIGNOFF", context={"task_name": "alu"})
    result = dispatch(sc)

    assert result.structured_conclusion["tapeout_ready"] is True
    assert (tmp_path / "reports/signoff_summary.md").is_file()


def test_unknown_stage_uses_fallback(tmp_path: Path) -> None:
    sc = _ctx(tmp_path, "SYNTH", context={"agent_name": "Diagnoser"})
    result = dispatch(sc)

    assert result.agent_name == "Diagnoser"
    assert "reports/synth_notes.md" in result.workspace_files
    assert result.recommended_next == "Confirm orchestrator approval and continue the remaining DAG."
