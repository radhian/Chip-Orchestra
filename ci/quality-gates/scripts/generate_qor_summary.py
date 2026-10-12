#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _read(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(errors="replace")


def _parse_float(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            raw = match.group(1).replace(",", "").strip()
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def parse_design(root: Path, repo: Path) -> dict:
    rel = str(root.relative_to(repo))
    timing = {"wns_ns": None, "timing_met": None, "reason": None, "source": None}
    area = {"area_um2": None, "reason": None, "source": None}
    power = {"power_mw": None, "reason": None, "source": None}

    sta_candidates = [root / "reports/sta.rpt", root / "reports/sta.txt"]
    for sta in sta_candidates:
        txt = _read(sta)
        if not txt:
            continue
        wns = _parse_float(txt, [r"Setup\s+WNS\s*:\s*([-+0-9.eE]+)", r"WNS\s*[:=]\s*([-+0-9.eE]+)", r"worst\s+slack\s*([-+0-9.eE]+)"])
        if wns is not None:
            timing["wns_ns"] = wns
            timing["timing_met"] = wns >= 0.0
            timing["source"] = str(sta.relative_to(repo))
            break
    if timing["wns_ns"] is None:
        timing["reason"] = "No STA report with parseable WNS found"

    synth_txt = _read(root / "reports/synth_stat.txt")
    if synth_txt:
        area_val = _parse_float(synth_txt, [r"Chip area for module .*?:\s*([-+0-9.eE]+)"])
        if area_val is not None:
            area["area_um2"] = area_val
            area["source"] = str((root / "reports/synth_stat.txt").relative_to(repo))
    if area["area_um2"] is None:
        summary_md = _read(root / "reports/flow_summary.md")
        if summary_md:
            area_val = _parse_float(summary_md, [r"Cell area:\s*\*\*([0-9\s,.]+)\s*µm²\*\*"])
            if area_val is not None:
                area["area_um2"] = area_val
                area["source"] = str((root / "reports/flow_summary.md").relative_to(repo))
    if area["area_um2"] is None:
        area["reason"] = "No synthesis/stat report with parseable area found"

    power_txt = _read(root / "reports/power_analysis.txt")
    if power_txt:
        power_val = _parse_float(power_txt, [r"TOTAL\s+POWER\s*=\s*([-+0-9.eE]+)\s*mW"])
        if power_val is not None:
            power["power_mw"] = power_val
            power["source"] = str((root / "reports/power_analysis.txt").relative_to(repo))
    if power["power_mw"] is None:
        power_rpt = _read(root / "reports/power.rpt")
        if power_rpt:
            try:
                parsed = json.loads(power_rpt)
                if isinstance(parsed.get("power_mw"), (int, float)):
                    power["power_mw"] = float(parsed["power_mw"])
                    power["source"] = str((root / "reports/power.rpt").relative_to(repo))
            except json.JSONDecodeError:
                pass
    if power["power_mw"] is None:
        power["reason"] = "No power report with parseable total power found"

    return {
        "design": root.name,
        "design_root": rel,
        "timing": timing,
        "area": area,
        "power": power,
    }


def to_markdown(summary: dict) -> str:
    lines = [
        "# Standardized timing/area/power summary",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "| Design | WNS (ns) | Timing | Area (um^2) | Power (mW) | Missing metric reasons |",
        "|---|---:|---|---:|---:|---|",
    ]
    for design in summary["designs"]:
        timing = design["timing"]
        area = design["area"]
        power = design["power"]
        timing_state = "MET" if timing["timing_met"] is True else ("VIOLATED" if timing["timing_met"] is False else "N/A")
        reasons = [x for x in [timing.get("reason"), area.get("reason"), power.get("reason")] if x]
        lines.append(
            "| {name} | {wns} | {state} | {area_val} | {power_val} | {reasons} |".format(
                name=design["design"],
                wns=(f"{timing['wns_ns']:.3f}" if isinstance(timing["wns_ns"], (int, float)) else "N/A"),
                state=timing_state,
                area_val=(f"{area['area_um2']:.3f}" if isinstance(area["area_um2"], (int, float)) else "N/A"),
                power_val=(f"{power['power_mw']:.3f}" if isinstance(power["power_mw"], (int, float)) else "N/A"),
                reasons=("; ".join(reasons) if reasons else "-"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--reports-dir", required=True)
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    repo = Path(__file__).resolve().parents[3]
    reports = Path(args.reports_dir)
    reports.mkdir(parents=True, exist_ok=True)

    design_roots = [repo / p for p in cfg.get("summary", {}).get("design_roots", [])]
    designs = [parse_design(root, repo) for root in design_roots]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema": "ci/quality-gates/schema/qor_summary.schema.json",
        "designs": designs,
    }

    (reports / "qor_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (reports / "qor_summary.md").write_text(to_markdown(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
