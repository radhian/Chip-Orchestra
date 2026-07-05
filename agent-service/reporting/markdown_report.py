"""Markdown report generation from a :class:`ReportContext`.

Renders the three phase-1 artifacts GarudaChip's report agent produced (adapted
to markdown-first):

* ``reports/final_design_report.md`` - evidence-backed design report
* ``reports/architecture_overview.md`` - module layout + flow
* ``reports/runbook.md`` - reproduction / debug instructions
"""
from __future__ import annotations

from typing import Dict

from .evidence import ReportContext

FINAL_REPORT_PATH = "reports/final_design_report.md"
ARCHITECTURE_PATH = "reports/architecture_overview.md"
RUNBOOK_PATH = "reports/runbook.md"


def _bullet_list(items) -> str:
    items = [str(i) for i in items]
    if not items:
        return "_none_"
    return "\n".join(f"- `{i}`" for i in items)


def _metrics_table(metrics: Dict) -> str:
    if not metrics:
        return "_No physical metrics were produced yet._"
    rows = ["| Metric | Value |", "| --- | --- |"]
    for key, value in metrics.items():
        rows.append(f"| {key} | {value} |")
    return "\n".join(rows)


def render_final_report(ctx: ReportContext) -> str:
    signoff_state = "✅ tapeout ready" if ctx.tapeout_ready else "⚠️ not tapeout ready"
    failed = ctx.signoff.get("failed") if isinstance(ctx.signoff, dict) else None
    sim = ctx.simulation or {}
    lines = [
        f"# Final Design Report — {ctx.task_name}",
        "",
        "## Overview",
        "",
        f"- **Task ID:** `{ctx.task_id}`",
        f"- **Top module:** `{ctx.top_module or 'n/a'}`",
        f"- **Signoff:** {signoff_state}",
        "",
        "## Design Brief",
        "",
        ctx.design_brief or "_No design brief provided._",
        "",
        "## Implementation Artifacts",
        "",
        "### RTL sources",
        _bullet_list(ctx.rtl_files),
        "",
        "### Testbenches",
        _bullet_list(ctx.tb_files),
        "",
        "## Verification Evidence",
        "",
        f"- Compiled: `{sim.get('compiled')}`",
        f"- Waveform produced: `{sim.get('waveform')}`",
        f"- Waveforms: {', '.join(f'`{w}`' for w in ctx.wave_files) or '_none_'}",
        "",
        "## Physical Results",
        "",
        _metrics_table(ctx.metrics),
        "",
        f"- GDS artifacts: {', '.join(f'`{g}`' for g in ctx.gds_files) or '_none_'}",
    ]
    if failed:
        lines += ["", f"- **Failed signoff checks:** {', '.join(failed)}"]
    lines += [
        "",
        "## Stage Reports",
        "",
        _bullet_list(sorted(ctx.stage_reports.keys())) if ctx.stage_reports else "_No structured stage reports._",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_architecture(ctx: ReportContext) -> str:
    lines = [
        f"# Architecture Overview — {ctx.task_name}",
        "",
        f"- **Top module:** `{ctx.top_module or 'n/a'}`",
        "",
        "## Module Inventory",
        "",
        _bullet_list(ctx.rtl_files),
        "",
        "## Design Notes",
        "",
        ctx.architecture_notes or "_No architecture note was generated during RTL_GEN._",
        "",
        "## Data Flow",
        "",
        "1. Spec is ingested and decomposed into interfaces and constraints.",
        "2. RTL is generated for the top module and its submodules.",
        "3. A self-checking testbench drives functional verification (SIM).",
        "4. LINT / SYNTH / PNR / DRC_LVS harden the design to GDSII.",
        "5. SIGNOFF and EXPORT assemble the evidence-backed reports.",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_runbook(ctx: ReportContext) -> str:
    top = ctx.top_module or "top"
    lines = [
        f"# Runbook — {ctx.task_name}",
        "",
        "## Reproduce the flow",
        "",
        "```bash",
        "# 1. Simulation (RTL + testbench)",
        f"iverilog -g2012 -o exports/sim.vvp -I rtl rtl/*.v tb/*.v",
        "vvp exports/sim.vvp   # writes waves/design.vcd",
        "",
        "# 2. Hardening (RTL -> GDSII)",
        "librelane --manual-pdk --pdk-root $PDK_ROOT exports/harden/chip/config.json",
        "```",
        "",
        "## Key artifacts",
        "",
        _bullet_list(ctx.rtl_files + ctx.tb_files + ctx.wave_files + ctx.gds_files),
        "",
        "## Debug tips",
        "",
        f"- If no `waves/design.vcd`, add `$dumpfile(\"design.vcd\"); $dumpvars(0, {top}_tb);` to the testbench.",
        "- If synthesis fails with a combinational-network error, check the detected `CLOCK_PORT`.",
        "- Review `logs/sim.log` and `logs/librelane.log` for the raw tool output.",
        "",
    ]
    return "\n".join(lines) + "\n"


def generate_reports(ctx: ReportContext) -> Dict[str, str]:
    """Return the {path: content} map of all markdown report artifacts."""
    return {
        FINAL_REPORT_PATH: render_final_report(ctx),
        ARCHITECTURE_PATH: render_architecture(ctx),
        RUNBOOK_PATH: render_runbook(ctx),
    }
