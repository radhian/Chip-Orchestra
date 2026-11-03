# CI quality gates (RTL/EDA)

This folder is dedicated to CI quality-gate assets (separate from runtime flow code).

## Included checks

- **Verilog lint + style** (`scripts/run_lint_and_style.py`)
  - Lint tool priority: `verilator`, then `iverilog`
  - Blocking checks: lint errors/non-zero exit, trailing whitespace, tab characters, CRLF files
  - Warning threshold is configurable in `config/quality-gates.json`
- **CDC/reset gate** (`scripts/run_cdc_reset_heuristics.py`)
  - Lightweight heuristic fallback (no full graph-based CDC/RDC engine)
  - Blocks on high-confidence findings: same signal written in multiple clock domains, suspicious async-reset block missing reset condition
- **QoR summary** (`scripts/generate_qor_summary.py`)
  - Generates standardized JSON and markdown with timing/area/power per configured design root
  - Missing metrics are explicitly set to `null` with reasons

## Local usage

From repository root:

```bash
python3 ci/quality-gates/scripts/run_lint_and_style.py \
  --config ci/quality-gates/config/quality-gates.json \
  --reports-dir ci/quality-gates/reports

python3 ci/quality-gates/scripts/run_cdc_reset_heuristics.py \
  --config ci/quality-gates/config/quality-gates.json \
  --reports-dir ci/quality-gates/reports

python3 ci/quality-gates/scripts/generate_qor_summary.py \
  --config ci/quality-gates/config/quality-gates.json \
  --reports-dir ci/quality-gates/reports
```

If local lint tools are unavailable, use `--allow-missing-tools` for non-blocking dry runs only.

## Outputs

- `lint_style_report.json`, `lint_style_report.md`
- `cdc_reset_report.json`, `cdc_reset_report.md`
- `qor_summary.json`, `qor_summary.md`

The JSON summary structure is defined in `schema/qor_summary.schema.json`.
