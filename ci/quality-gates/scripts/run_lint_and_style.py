#!/usr/bin/env python3
import argparse
import glob
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def collect_group_files(repo: Path, group: dict) -> list[Path]:
    files: set[Path] = set()
    for pattern in group.get("patterns", []):
        for hit in glob.glob(str(repo / pattern), recursive=True):
            p = Path(hit)
            if p.is_file():
                files.add(p)
    return sorted(files)


def pick_tool(preference: list[str]) -> str | None:
    for tool in preference:
        if shutil.which(tool):
            return tool
    return None


def run_lint(tool: str, config: dict, include_dirs: list[str], files: list[Path], repo: Path) -> dict:
    if tool == "verilator":
        cmd = [tool, *config["lint"].get("verilator_args", [])]
        for d in include_dirs:
            cmd.append(f"-I{repo / d}")
        cmd.extend(str(f) for f in files)
        error_re, warn_re = r"%Error", r"%Warning"
    else:
        cmd = [tool, *config["lint"].get("iverilog_args", [])]
        for d in include_dirs:
            cmd.extend(["-I", str(repo / d)])
        cmd.extend(str(f) for f in files)
        error_re, warn_re = r"\berror:\b", r"\bwarning:\b"

    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    errors = len(re.findall(error_re, output, flags=re.IGNORECASE))
    warnings = len(re.findall(warn_re, output, flags=re.IGNORECASE))
    return {
        "command": cmd,
        "exit_code": proc.returncode,
        "errors": errors,
        "warnings": warnings,
        "output": output.strip(),
    }


def run_style(files: list[Path], max_line_len: int, style_cfg: dict, repo: Path) -> dict:
    blocking, warnings = [], []
    block_crlf = bool(style_cfg.get("block_crlf", True))
    block_trailing = bool(style_cfg.get("block_trailing_whitespace", False))
    block_tabs = bool(style_cfg.get("block_tabs", False))
    for fp in files:
        text = fp.read_text(errors="replace")
        rel = str(fp.relative_to(repo))
        if "\r\n" in text and block_crlf:
            blocking.append(f"{rel}: contains CRLF line endings")
        for idx, line in enumerate(text.splitlines(), start=1):
            if line.endswith(" "):
                msg = f"{rel}:{idx}: trailing whitespace"
                (blocking if block_trailing else warnings).append(msg)
            if "\t" in line:
                msg = f"{rel}:{idx}: tab character detected"
                (blocking if block_tabs else warnings).append(msg)
            if max_line_len > 0 and len(line) > max_line_len:
                warnings.append(f"{rel}:{idx}: line length {len(line)} > {max_line_len}")
    return {"blocking": blocking, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--reports-dir", required=True)
    parser.add_argument("--allow-missing-tools", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[3]
    config = load_config(Path(args.config))
    reports_dir = Path(args.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    groups = []
    all_files: list[Path] = []
    for group in config.get("rtl_groups", []):
        files = collect_group_files(repo, group)
        groups.append({"name": group["name"], "files": [str(p.relative_to(repo)) for p in files], "include_dirs": group.get("include_dirs", [])})
        all_files.extend(files)

    style_cfg = config.get("style", {})
    style = run_style(all_files, int(style_cfg.get("warn_line_length", 0) or 0), style_cfg, repo)

    lint_tool = pick_tool(config.get("lint", {}).get("tool_preference", ["verilator", "iverilog"]))
    lint_runs = []
    blocking = list(style["blocking"])
    if lint_tool is None:
        msg = "No lint tool found from preference list. Install verilator or iverilog."
        if args.allow_missing_tools:
            lint_runs.append({"tool": "missing", "skipped": True, "reason": msg})
        else:
            blocking.append(msg)
    else:
        for group in groups:
            files = [repo / p for p in group["files"] if Path(p).suffix in {".v", ".sv"}]
            if not files:
                lint_runs.append({"group": group["name"], "tool": lint_tool, "skipped": True, "reason": "No files discovered"})
                continue
            result = run_lint(lint_tool, config, group["include_dirs"], files, repo)
            lint_runs.append({"group": group["name"], "tool": lint_tool, **result})
            if result["exit_code"] != 0 or result["errors"] > 0:
                blocking.append(f"{group['name']}: lint errors={result['errors']} exit_code={result['exit_code']}")

    warning_count = sum(int(r.get("warnings", 0)) for r in lint_runs if isinstance(r, dict)) + len(style["warnings"])
    warning_threshold = int(config.get("lint", {}).get("warning_threshold", 0) or 0)
    warning_blocked = warning_threshold >= 0 and warning_count > warning_threshold
    if warning_blocked:
        blocking.append(f"Warning threshold exceeded: {warning_count} > {warning_threshold}")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not blocking else "fail",
        "blocking_findings": blocking,
        "warning_count": warning_count,
        "warning_threshold": warning_threshold,
        "groups": groups,
        "style": style,
        "lint_runs": lint_runs,
    }

    (reports_dir / "lint_style_report.json").write_text(json.dumps(summary, indent=2) + "\n")

    md_lines = [
        "# RTL lint + style quality gate",
        "",
        f"- Status: **{summary['status'].upper()}**",
        f"- Warning threshold: `{warning_threshold}` (observed `{warning_count}`)",
        "",
        "## Blocking findings",
    ]
    if blocking:
        md_lines.extend([f"- {b}" for b in blocking])
    else:
        md_lines.append("- None")

    md_lines.append("\n## Lint groups")
    for run in lint_runs:
        if run.get("skipped"):
            md_lines.append(f"- `{run.get('group', 'n/a')}`: skipped ({run.get('reason', 'n/a')})")
            continue
        md_lines.append(
            f"- `{run['group']}`: tool={run['tool']} exit={run['exit_code']} errors={run['errors']} warnings={run['warnings']}"
        )

    (reports_dir / "lint_style_report.md").write_text("\n".join(md_lines) + "\n")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
