#!/usr/bin/env python3
import argparse
import glob
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    return text


def collect_files(repo: Path, patterns: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        for hit in glob.glob(str(repo / pattern), recursive=True):
            p = Path(hit)
            if p.is_file():
                files.add(p)
    return sorted(files)


def analyze_file(path: Path, reset_regex: str, repo: Path) -> dict:
    text = strip_comments(path.read_text(errors="replace"))
    rel = str(path.relative_to(repo))
    always_blocks = re.findall(r"always\s*@\((.*?)\)\s*begin(.*?)end", text, flags=re.DOTALL | re.IGNORECASE)

    assignments_by_signal: dict[str, set[str]] = defaultdict(set)
    critical, warnings = [], []

    for sensitivity, body in always_blocks:
        edges = re.findall(r"(?:posedge|negedge)\s+([A-Za-z_][A-Za-z0-9_$]*)", sensitivity)
        reset_edges = [e for e in edges if re.search(reset_regex, e, flags=re.IGNORECASE)]
        clock_edges = [e for e in edges if e not in reset_edges]

        assigned = re.findall(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b\s*<=", body)
        for sig in assigned:
            for clk in clock_edges:
                assignments_by_signal[sig].add(clk)

        if reset_edges:
            head = "\n".join([ln.strip() for ln in body.splitlines()[:8]])
            if not any(re.search(rf"\b{re.escape(rst)}\b", head) for rst in reset_edges):
                critical.append(
                    f"{rel}: async reset edge in sensitivity ({', '.join(reset_edges)}) but reset not checked near block start"
                )
        elif clock_edges:
            warnings.append(f"{rel}: sequential always block has no explicit reset ({', '.join(clock_edges)})")

    for sig, clocks in assignments_by_signal.items():
        if len(clocks) > 1:
            critical.append(f"{rel}: signal '{sig}' written in multiple clock domains: {sorted(clocks)}")

    return {
        "file": rel,
        "always_blocks": len(always_blocks),
        "critical": critical,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--reports-dir", required=True)
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text())
    repo = Path(__file__).resolve().parents[3]
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    reset_regex = config.get("cdc_reset", {}).get("reset_regex", "(rst|reset)")
    all_patterns = []
    for group in config.get("rtl_groups", []):
        all_patterns.extend(group.get("patterns", []))

    files = collect_files(repo, all_patterns)
    per_file = [analyze_file(fp, reset_regex, repo) for fp in files]

    critical = [item for pf in per_file for item in pf["critical"]]
    warnings = [item for pf in per_file for item in pf["warnings"]]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not critical else "fail",
        "limitations": [
            "Heuristic parser only: no netlist/formal CDC graph analysis.",
            "May miss generated code/macros and can report false positives for intentional multi-clock structures.",
            "Reset checks only verify simple pattern presence near sequential block entry.",
        ],
        "files_scanned": len(files),
        "critical_findings": critical,
        "warning_findings": warnings,
        "per_file": per_file,
    }

    (reports_dir / "cdc_reset_report.json").write_text(json.dumps(summary, indent=2) + "\n")

    md = [
        "# CDC/Reset heuristic quality gate",
        "",
        f"- Status: **{summary['status'].upper()}**",
        f"- Files scanned: `{summary['files_scanned']}`",
        "",
        "## Limitations",
    ]
    md.extend([f"- {x}" for x in summary["limitations"]])
    md.append("\n## Critical findings")
    md.extend([f"- {x}" for x in critical] if critical else ["- None"])
    md.append("\n## Warning findings")
    md.extend([f"- {x}" for x in warnings] if warnings else ["- None"])

    (reports_dir / "cdc_reset_report.md").write_text("\n".join(md) + "\n")
    return 1 if critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
