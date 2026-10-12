# RTL/EDA CI quality gates

Chip Orchestra includes a dedicated CI quality-gate bundle under:

- `ci/quality-gates/`
- workflow: `.github/workflows/quality-gates.yml`

## What runs in CI

1. **RTL lint + style gate**
   - Script: `ci/quality-gates/scripts/run_lint_and_style.py`
   - Lint tool order: `verilator` then `iverilog`
   - Blocking failures:
     - lint errors / non-zero linter exit
     - trailing whitespace
     - tab characters
     - CRLF line endings

2. **CDC/reset gate (best-available fallback)**
   - Script: `ci/quality-gates/scripts/run_cdc_reset_heuristics.py`
   - This is a lightweight static heuristic checker (not full structural/formal CDC/RDC).
   - Blocking failures:
     - same signal written from multiple clock domains
     - async-reset edge sensitivity without visible reset condition near block start
   - Limitations are emitted in the report and should be considered when triaging findings.

3. **Standardized QoR summary artifact**
   - Script: `ci/quality-gates/scripts/generate_qor_summary.py`
   - Outputs:
     - machine-readable JSON: `ci/quality-gates/reports/qor_summary.json`
     - human-readable markdown: `ci/quality-gates/reports/qor_summary.md`
   - Fields include timing (WNS + MET/VIOLATED), area, and power.
   - Missing values are explicitly `null` with a reason.

## Local run

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

For local dry-runs without installed lint binaries only:

```bash
python3 ci/quality-gates/scripts/run_lint_and_style.py \
  --config ci/quality-gates/config/quality-gates.json \
  --reports-dir ci/quality-gates/reports \
  --allow-missing-tools
```

## Interpreting failures

- `lint_style_report.json`: blocking/warning findings per RTL group and linter output status.
- `cdc_reset_report.json`: heuristic critical findings and known limitations.
- `qor_summary.json`: standardized timing/area/power snapshot for configured design roots.

A non-zero exit from lint or CDC/reset scripts is treated as a blocking CI gate failure.
