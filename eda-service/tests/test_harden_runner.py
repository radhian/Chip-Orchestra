from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runner import CommandResult
from toolchain.harden_runner import run_harden
from workspace import ensure_workspace


FAKE_METRICS = {
    "design__die__area": 12345,
    "design__core__area": 10000,
    "design__instance__utilization": 42.1,
    "timing__setup__ws": 0.08,
    "power__total": 3.7,
    "magic__drc_error__count": 0,
    "route__drc_errors": 0,
    "lvs__total__errors": 0,
}


class FakeHardenRunner:
    """Fake runner that writes a fake GDS + metrics.json under the run dir."""

    def __init__(self, *, produce_gds: bool = True, clean: bool = True):
        self.calls: List[list] = []
        self.produce_gds = produce_gds
        self.clean = clean

    def run(self, args, *, cwd=None, timeout=None, env=None) -> CommandResult:
        self.calls.append([str(a) for a in args])
        if cwd is not None and self.produce_gds:
            final = Path(cwd) / "runs" / "RUN_1" / "final" / "gds"
            final.mkdir(parents=True, exist_ok=True)
            (final / "uart_top.gds").write_text("FAKE_GDS")
            render = Path(cwd) / "runs" / "RUN_1" / "final" / "render"
            render.mkdir(parents=True, exist_ok=True)
            (render / "layout.png").write_bytes(b"\x89PNG\r\n")
            metrics = dict(FAKE_METRICS)
            if not self.clean:
                metrics["magic__drc_error__count"] = 3
            (Path(cwd) / "runs" / "RUN_1" / "metrics.json").write_text(json.dumps(metrics))
        return CommandResult(args=[str(a) for a in args], returncode=0, stdout="LibreLane flow complete\n")


def _seed(tmp_path: Path) -> Path:
    ws = ensure_workspace("task-hard", tmp_path)
    (ws / "rtl" / "uart_top.v").write_text(
        "module uart_top(input clk, input rst, output reg q);\n"
        "  always @(posedge clk) q <= rst;\n"
        "endmodule\n"
    )
    return ws


def test_run_harden_produces_gds_metrics_and_signoff(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    runner = FakeHardenRunner(produce_gds=True, clean=True)

    report = run_harden(ws, top="uart_top", clock_port="clk", clock_period=20.0, runner=runner, stage="SYNTH")

    assert report.stage == "SYNTH"
    assert report.top == "uart_top"
    assert report.gds == "gds/uart_top.gds"
    assert report.png == "gds/uart_top.png"
    assert report.tapeout_ready is True
    assert report.signoff["clean"] is True
    assert report.metrics["die_area_um2"] == 12345
    assert report.metrics["power_mw"] == 3.7
    assert (ws / "gds" / "uart_top.gds").is_file()
    paths = {a["path"] for a in report.artifacts}
    assert {"gds/uart_top.gds", "gds/uart_top.png", "logs/librelane.log"} <= paths
    # config.json was synthesized
    cfg = json.loads((ws / "exports" / "harden" / "chip" / "config.json").read_text())
    assert cfg["DESIGN_NAME"] == "uart_top"
    assert cfg["CLOCK_PORT"] == "clk"


def test_run_harden_dirty_signoff_not_tapeout_ready(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    runner = FakeHardenRunner(produce_gds=True, clean=False)

    report = run_harden(ws, top="uart_top", runner=runner, stage="DRC_LVS")

    assert report.stage == "DRC_LVS"
    assert report.signoff["clean"] is False
    assert report.tapeout_ready is False
    assert "magic_drc" in report.signoff["failed"]


def test_run_harden_missing_librelane(tmp_path: Path) -> None:
    ws = _seed(tmp_path)

    class MissingRunner:
        def run(self, args, *, cwd=None, timeout=None, env=None):
            return CommandResult(args=[str(a) for a in args], returncode=127, not_found=True)

    report = run_harden(ws, top="uart_top", runner=MissingRunner(), stage="PNR")

    assert report.stage == "PNR"
    assert "librelane not available" in report.errors
    assert report.tapeout_ready is False


def test_run_harden_autodetects_top(tmp_path: Path) -> None:
    ws = ensure_workspace("task-auto", tmp_path)
    (ws / "rtl" / "leaf.v").write_text("module leaf(input a, output b); assign b=a; endmodule\n")
    (ws / "rtl" / "chip_top.v").write_text(
        "module chip_top(input clk); leaf u(.a(clk), .b()); endmodule\n"
    )
    runner = FakeHardenRunner(produce_gds=False)
    report = run_harden(ws, runner=runner, stage="SYNTH")
    assert report.top == "chip_top"
