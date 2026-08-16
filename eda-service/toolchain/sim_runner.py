"""RTL simulation runner (iverilog + vvp).

Ports GarudaChip's ``backend/garuda_api/sim.py`` run logic into Chip Orchestra's
stage-oriented model: compile every source with ``iverilog -g2012``, run the
resulting image with ``vvp``, capture the combined log, detect the ``design.vcd``
waveform and (best-effort) parse a compact waveform summary.

All subprocess calls go through an injected :class:`CommandRunner` so tests can
run without iverilog/vvp installed.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from runner import CommandRunner, default_runner

from .artifacts import register_artifact
from .harden_runner import _parse_rtl, pick_top
from .memimg import infer_size
from .reports import LintReport, SimReport
from . import vcd

RTL_EXT = (".v", ".sv", ".vh", ".svh")
COMPILE_EXT = (".v", ".sv")



class _VCDTooBig(Exception):
    """The dump is too large to parse in memory; results are still valid."""


def _max_vcd_bytes() -> int:
    try:
        return max(1, int(os.getenv("SIM_MAX_VCD_MB", "256"))) * 1024 * 1024
    except ValueError:
        return 256 * 1024 * 1024


def _vcd_too_big(size_bytes: int) -> str:
    """Message when design.vcd is too large to parse, or "" when it is fine.

    A UART tb that simulates REAL baud timing (CLK/BAUD = 434 clocks per bit)
    runs ~8M cycles for one 32x32 frame; with `$dumpvars(0, tb)` dumping the
    whole hierarchy that produced a 5.7 GB dump, and parsing it OOM-killed the
    service. The fix belongs in the testbench, so say exactly what to change."""
    cap = _max_vcd_bytes()
    if size_bytes <= cap:
        return ""
    return (
        f"design.vcd is {size_bytes / (1 << 30):.2f} GB (cap "
        f"{cap // (1 << 20)} MB) — waveform preview SKIPPED so the parse cannot exhaust memory. "
        "The simulation's own results (TEST PASSED/FAILED, waves/chip_output.mem, the golden "
        "comparison) are UNAFFECTED. To get a waveform back, make the testbench cheaper: "
        "(1) narrow the dump — `$dumpvars(1, tb)` or name the few signals of interest instead "
        "of `$dumpvars(0, tb)`, which dumps the entire hierarchy; "
        "(2) do not simulate real baud timing — override the divider for simulation "
        "(e.g. `defparam`/`localparam BAUD_DIV = 8`) so a byte costs ~80 cycles instead of "
        "~4340; the framing logic is exercised identically; "
        "(3) bound the watchdog — `repeat (100000000)` is 100M cycles; size it to the real "
        "transfer (bytes x 10 x BAUD_DIV plus margin); "
        "(4) if a long run is genuinely needed, `$dumpoff`/`$dumpon` around the interesting "
        "window."
    )


def _affected_pattern(bad: list, n: int) -> str:
    """The STRUCTURE of the affected index set — 'every odd byte' is a clue,
    'scattered' is not."""
    if len(bad) == n:
        return "every value"
    if len(bad) > 1:
        if all(i % 2 for i in bad):
            return "every ODD index"
        if all(i % 2 == 0 for i in bad):
            return "every EVEN index"
        step = bad[1] - bad[0]
        if step > 1 and all(b - a == step for a, b in zip(bad, bad[1:])):
            return f"every {step}th index (from {bad[0]})"
    if bad == list(range(bad[0], bad[0] + len(bad))):
        if bad[0] == 0:
            return f"the FIRST {len(bad)} values"
        if bad[-1] == n - 1:
            return f"the LAST {len(bad)} values"
        return f"a contiguous run at {bad[0]}..{bad[-1]}"
    return ""


def _mismatch_law(golden: list, chip: list) -> str:
    """The systematic RELATION between chip and golden, when one exists.

    "403 of 900 values differ" sends a repair agent hunting the entire datapath;
    it burned rounds guessing. "chip == (golden>>1)|0x80 on every ODD index" is
    a one-bit serial misalignment with the idle bit shifted into the MSB, and
    points straight at the byte boundary in the serialiser. A law that holds for
    EVERY mismatch is a far stronger signal than any number of sample diffs, so
    derive it here rather than hoping the agent spots it in twelve hex pairs."""
    n = min(len(golden), len(chip))
    bad = [i for i in range(n) if golden[i] != chip[i]]
    if not bad:
        return ""
    M = 0xFF

    # Index-shift is a different CLASS of bug (latency/ordering, not arithmetic),
    # so test it first and against the whole stream.
    for k in range(1, 5):
        if n > k * 2:
            if all(chip[i] == golden[i - k] for i in range(k, n)):
                return (f"chip[i] == golden[i-{k}] for the whole stream — the chip output LAGS "
                        f"the golden by {k} sample(s). Either the testbench samples before the "
                        f"pipeline has filled, or there is one extra register stage; this is a "
                        f"latency/alignment bug, NOT a datapath bug.")
            if all(chip[i] == golden[i + k] for i in range(0, n - k)):
                return (f"chip[i] == golden[i+{k}] for the whole stream — the chip output LEADS "
                        f"the golden by {k} sample(s): a missing register stage, or the "
                        f"testbench captures one sample too late.")

    G = [golden[i] for i in bad]
    C = [chip[i] for i in bad]
    g0, c0 = G[0], C[0]
    cands = []

    # Stuck-bit laws first: when a stuck bit and a constant offset both fit the
    # data (they coincide whenever the affected bit was already 0), "bit 6 is
    # tied high" is a structural claim a repair can act on, while "adds 64"
    # sends it looking for arithmetic that is not there.
    o = c0 & (~g0 & M)
    if o:
        cands.append((f"chip == golden | 0x{o:02x}  [bit(s) STUCK HIGH — a tied or undriven line]",
                      lambda g, o=o: (g | o) & M))
    a = M & ~(g0 & (~c0 & M))
    if a != M:
        cands.append((f"chip == golden & 0x{a:02x}  [bit(s) STUCK LOW or a truncated width]",
                      lambda g, a=a: g & a))
    d = (c0 - g0) & M
    cands.append((f"chip == (golden + 0x{d:02x}) & 0xFF  [constant offset of {d}: a bias/rounding "
                  f"term the RTL adds and the model does not]", lambda g, d=d: (g + d) & M))
    x = g0 ^ c0
    cands.append((f"chip == golden ^ 0x{x:02x}  [fixed bit(s) flipped: an inverted signal or "
                  f"wrong polarity on those bit lines]", lambda g, x=x: g ^ x))
    cands.append(("chip == 0xFF - golden  [output inverted]", lambda g: M - g))
    cands.append(("chip == bit_reverse(golden)  [LSB-first vs MSB-first: the serialiser shifts "
                  "the byte out the wrong way round]",
                  lambda g: int(f"{g:08b}"[::-1], 2)))
    for s in (1, 2, 3, 4):
        fill = (M << (8 - s)) & M
        cands.append((f"chip == (golden >> {s}) | 0x{fill:02x}  [the byte is sampled {s} bit(s) "
                      f"LATE and the idle/stop bit (1) is shifted into the top: a byte-boundary "
                      f"off-by-{s} in the serial shift register]",
                      lambda g, s=s, f=fill: ((g >> s) | f) & M))
        cands.append((f"chip == golden >> {s}  [value divided by {1 << s}: an extra right shift "
                      f"in the datapath]", lambda g, s=s: g >> s))
        cands.append((f"chip == (golden << {s}) & 0xFF  [value multiplied by {1 << s} and "
                      f"truncated: a missing right shift, or sampled {s} bit(s) EARLY]",
                      lambda g, s=s: (g << s) & M))

    where = _affected_pattern(bad, n)
    scope = f" on {where}" if where else ""
    for desc, fn in cands:
        try:
            if all(fn(g) == c for g, c in zip(G, C)):
                return (f"SYSTEMATIC: {desc}{scope} — holds for ALL {len(bad)} mismatching "
                        f"value(s), so this is one deterministic transform, not noise. Fix that "
                        f"transform; do not re-derive the datapath.")
        except Exception:  # noqa: BLE001
            continue
    if where:
        return (f"mismatches land on {where} — no single arithmetic/bitwise law explains the "
                f"values, so look at what distinguishes those positions (phase, handshake, "
                f"alternating buffer) rather than at the arithmetic.")
    return ""


def _mismatch_shape(golden: list, chip: list, workspace: Path) -> str:
    """WHERE the chip disagrees with golden, not just that it does.

    Twelve truncated `index N: golden=X chip=Y` lines tell a repair agent
    nothing about the CLASS of bug, and it burned ten rounds guessing. 34 of
    1024 values differing, all in columns 0/1/31 and row 0, is a border-padding
    bug and says so at a glance; 1024 of 1024 is a broken datapath.
    """
    n = min(len(golden), len(chip))
    bad = [i for i in range(n) if golden[i] != chip[i]]
    if not bad:
        return ""
    side = infer_size(workspace, n, max(max(golden[:n], default=0), 1))
    parts = [f"{len(bad)} of {n} values differ ({100.0 * len(bad) / n:.1f}%)"]
    if side and side > 1 and n % side == 0:
        rows = sorted({i // side for i in bad})
        cols = sorted({i % side for i in bad})
        edge_cols = {0, 1, side - 2, side - 1}
        edge_rows = {0, 1, n // side - 2, n // side - 1}
        parts.append(f"grid {side}x{n // side}")
        parts.append("rows " + (",".join(map(str, rows[:8])) + ("…" if len(rows) > 8 else "")))
        parts.append("cols " + (",".join(map(str, cols[:8])) + ("…" if len(cols) > 8 else "")))
        if set(cols) <= edge_cols or set(rows) <= edge_rows:
            parts.append("ALL mismatches are on the BORDER — this is an edge/padding rule "
                         "difference (the golden model's border handling, e.g. replicate/clamp "
                         "padding, is not what the RTL does), NOT a datapath bug: the interior "
                         "pixels all match")
        elif len(bad) == n:
            parts.append("EVERY value differs — the datapath or the output ordering is wrong, "
                         "not an edge case")
    return "; ".join(parts)


def rtl_fingerprint(rtl_dir: Path) -> str:
    """Content hash of the synthesizable RTL — what a SIM result belongs to."""
    import hashlib
    h = hashlib.sha256()
    for f in sorted(Path(rtl_dir).glob("*.v")) + sorted(Path(rtl_dir).glob("*.vh")):
        try:
            h.update(f.name.encode())
            h.update(f.read_bytes())
        except OSError:
            continue
    return h.hexdigest()


def _record_verified_rtl(workspace: Path) -> None:
    """Stamp the RTL that SIM actually verified.

    RTL_REPAIR is an AGENT stage that runs between SIM and SYNTH and rewrites
    rtl/, and nothing re-runs SIM afterwards — so the GDS was being built from
    code that never passed simulation. Recording the verified fingerprint lets
    hardening refuse RTL that changed after it was verified.
    """
    try:
        ctx = workspace / "context"
        ctx.mkdir(parents=True, exist_ok=True)
        (ctx / "verified_rtl.json").write_text(json.dumps({
            "sha256": rtl_fingerprint(workspace / "rtl"),
            "note": "the RTL fingerprint at the moment SIM passed; hardening must match it",
        }, indent=2))
    except OSError:
        pass

def _rtl_modules(rtl_dir: Path) -> set:
    """Every module name the RTL declares."""
    try:
        return set(_parse_rtl(rtl_dir)["defs"])
    except Exception:  # noqa: BLE001
        return set()


def _iverilog_bin() -> str:
    return os.getenv("IVERILOG_PATH") or os.getenv("IVERILOG_BIN", "iverilog")


def _vvp_bin() -> str:
    return os.getenv("VVP_PATH") or os.getenv("VVP_BIN", "vvp")


def _sim_timeout() -> int:
    try:
        return int(os.getenv("EDA_JOB_TIMEOUT_SIM", "120"))
    except ValueError:
        return 120


def run_simulation(
    workspace: Path,
    sources: List[Path],
    top: str,
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
) -> SimReport:
    """Compile + run the given ``sources`` and return a :class:`SimReport`.

    ``workspace`` is the standardized task workspace. Compilation writes
    ``exports/sim.vvp``; simulation runs with the WORKSPACE ROOT as CWD so the
    design-root-relative paths the RTL uses actually resolve —
    ``$readmemh("rtl/weights.mem")`` and testbench dumps like
    ``$writememh("waves/chip_output.mem")``. (Running from ``waves/`` broke
    every ``rtl/*.mem`` load: the weights read as X and the self-check failed
    on garbage outputs.) A bare ``$dumpfile("design.vcd")`` lands at the root
    and is moved into ``waves/`` afterwards.
    """
    opts = opts or {}
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    waves_dir = workspace / "waves"
    logs_dir = workspace / "logs"
    exports_dir = workspace / "exports"
    for d in (waves_dir, logs_dir, exports_dir):
        d.mkdir(parents=True, exist_ok=True)

    report = SimReport(top=top)
    artifacts: List[dict] = []

    vfiles = [Path(p) for p in sources if Path(p).suffix.lower() in COMPILE_EXT]
    if not vfiles:
        report.summary = "No .v/.sv sources found to simulate."
        report.errors.append("no synthesizable/testbench sources present in workspace")
        return report

    # `top` arrives from spec/spec.json, which SPEC_INGEST derives from the TASK
    # NAME — it is not necessarily a module the design declares. When it is not,
    # BOTH selectors below miss (no `<slug>_tb.v`, and no tb instantiates the
    # slug), the "largest tb" fallback picks whichever UNIT testbench happens to
    # be biggest, and SIM reports a green run for a single IP: no chip output,
    # no waveform, chip-vs-golden never compared. Resolve the name the RTL
    # actually declares before choosing anything.
    structural_top = pick_top(rtl_dir) if rtl_dir.is_dir() else ""
    if structural_top and top != structural_top:
        declared = _rtl_modules(rtl_dir)
        if top not in declared:
            report.warnings.append(
                f"requested top '{top}' is not a module in rtl/; using the structural "
                f"top '{structural_top}' to select the chip-level testbench")
            top = structural_top
            report.top = top

    # ONE testbench per simulation: the flow also writes per-IP UNIT testbenches
    # (tb/<module>_tb.v) for generation-time verify — compiling them all together
    # runs every tb simultaneously and any unit tb's $fatal kills the MAIN run.
    # Keep only the TOP testbench: <top>_tb.* when present, else the tb that
    # instantiates the top module, else the largest tb.
    tbs = [p for p in vfiles if "tb" in p.parts or p.stem.endswith("_tb")]
    if len(tbs) > 1:
        chosen = next((p for p in tbs if top and p.stem == f"{top}_tb"), None)
        if chosen is None and top:
            for p in tbs:
                try:
                    if re.search(rf"\b{re.escape(top)}\s+(#\s*\(|\w+\s*\()", p.read_text(errors="replace")):
                        chosen = p
                        break
                except OSError:
                    continue
        if chosen is None:
            # Nothing instantiates the top: whatever we pick is a UNIT tb, so the
            # chip is NOT being simulated. Say so — a silent pass here is how a
            # single-IP run got reported as a verified chip.
            chosen = max(tbs, key=lambda p: p.stat().st_size if p.exists() else 0)
            report.warnings.append(
                f"NO chip-level testbench instantiates top '{top}' — falling back to "
                f"{chosen.name}, which exercises one IP, not the chip: expect no "
                f"chip_output.mem and no golden comparison")
        dropped = [p.name for p in tbs if p != chosen]
        vfiles = [p for p in vfiles if p not in tbs or p == chosen]
        report.warnings.append(
            f"multiple testbenches found; simulating {chosen.name} (unit tbs excluded: {', '.join(dropped)})")

    vvp_path = exports_dir / "sim.vvp"
    vcd_path = waves_dir / "design.vcd"
    # Stale outputs must never masquerade as this run's results: the chip
    # output dump (and its render) belongs to THE RUN THAT PRODUCED IT — an old
    # chip_output.mem once showed up (and compared) as if the new tb had
    # written it. golden_output.* stays: GOLDEN_GEN produces it, not the sim.
    for stale in (vvp_path, vcd_path, workspace / "design.vcd",
                  waves_dir / "chip_output.mem", waves_dir / "chip_output.png"):
        if stale.exists():
            stale.unlink()

    # The elaboration ROOT must be the TESTBENCH, never the DUT: `-s <dut>`
    # elaborated the bare design with dangling inputs, vvp ran NOTHING, printed
    # nothing, and the silent run slipped through as a pass.
    tb_files = [p for p in vfiles if "tb" in p.parts or p.stem.endswith("_tb")]
    sim_root = tb_files[0].stem if tb_files else top

    log: List[str] = []
    inc = f"-I{rtl_dir}"
    compile_cmd = [_iverilog_bin(), "-g2012", "-o", str(vvp_path), inc]
    if sim_root:
        compile_cmd += ["-s", sim_root]
    compile_cmd += [str(p) for p in vfiles]
    log.append("$ " + " ".join(
        ["iverilog", "-g2012", "-o", "exports/sim.vvp", "-I rtl"]
        + (["-s", sim_root] if sim_root else [])
        + [p.name for p in vfiles]
    ))

    timeout = _sim_timeout()
    compile_res = runner.run(compile_cmd, cwd=workspace, timeout=timeout)
    if compile_res.not_found:
        log.append("iverilog is not installed / not on PATH.")
        report.errors.append("iverilog not available")
        report.summary = "Simulation could not run: iverilog not available."
        _finalize_log(report, logs_dir, log, artifacts)
        return report
    if compile_res.timed_out:
        log.append(f"(compile timed out after {timeout}s)")
        report.errors.append("compile timeout")
        report.summary = "Simulation compile timed out."
        _finalize_log(report, logs_dir, log, artifacts)
        return report

    log.append(compile_res.output or "(compiled, no warnings)")
    if compile_res.returncode != 0:
        report.compiled = False
        report.errors.append("compile failed")
        report.summary = "RTL compilation failed; fix the errors in the log."
        report.warnings.append("fix the compile errors above, then run again")
        _finalize_log(report, logs_dir, log, artifacts)
        return report

    report.compiled = True
    log.append("$ vvp exports/sim.vvp")
    run_res = runner.run([_vvp_bin(), str(vvp_path)], cwd=workspace, timeout=timeout)
    # A tb that dumps a bare "design.vcd" writes it at the workspace root now —
    # move it to the standard waves/ location.
    root_vcd = workspace / "design.vcd"
    if root_vcd.is_file() and not vcd_path.is_file():
        root_vcd.replace(vcd_path)
    passed = None
    if run_res.not_found:
        log.append("vvp is not installed / not on PATH.")
        report.warnings.append("vvp not available; compiled but not executed")
    elif run_res.timed_out:
        log.append("(simulation timed out — check for a missing $finish)")
        report.warnings.append("simulation timeout")
        passed = False
    else:
        if run_res.stdout.strip():
            log.append(run_res.stdout.strip())
        if run_res.stderr.strip():
            log.append("[stderr] " + run_res.stderr.strip())
        # The self-checking testbench's VERDICT — this is what makes the SIM
        # stage honest instead of "it ran, therefore success".
        out_text = run_res.stdout + "\n" + run_res.stderr
        import re as _re
        # A bare "mismatch" also matches "0 mismatches" — a testbench that
        # honestly reports a clean compare was marked FAILED while the golden
        # check right below it said the output matched value-for-value. Only a
        # NON-ZERO count is a failure.
        if _re.search(r"FAILED|\$fatal|ERROR:|assert(ion)?\s+fail"
                      r"|(?<![0-9])[1-9][0-9]*\s+mismatch"
                      r"|\bmismatch(?!es\b)(?!\s*[:=]?\s*0\b)", out_text, _re.I):
            passed = False
        elif _re.search(r"TEST\s+PASSED|ALL\s+TESTS?\s+PASSED", out_text, _re.I):
            passed = True
        elif tb_files:
            # A testbench that ran but printed NO verdict proves nothing —
            # silence is not success (a silent run is how the fake pass
            # happened). Treated as a failure so the repair loop engages.
            passed = False
            log.append("(testbench printed no TEST PASSED/FAILED verdict — treated as FAILED; "
                       "a self-checking tb must $display its verdict)")

    if vcd_path.is_file():
        report.waveform = True
        vcd_bytes = vcd_path.stat().st_size
        oversized = _vcd_too_big(vcd_bytes)
        if oversized:
            # `read_text()` on the whole dump is what actually died: a 5.7 GB
            # design.vcd became a 5.7 GB Python string and the OOM killer took
            # the WHOLE eda-service down mid-stage, leaving SIM orphaned and the
            # task showing RUNNING forever. The waveform is only a PREVIEW —
            # pass/fail, chip_output.mem and the golden comparison all come from
            # stdout and .mem files — so skipping the parse costs the picture and
            # nothing else. Never trade the service for a thumbnail.
            log.append(oversized)
            report.warnings.append(oversized)
        try:
            if oversized:
                raise _VCDTooBig(oversized)
            wave_json = vcd.to_wave_json(vcd_path.read_text(errors="replace"))
            # The full trace data is BIG (blew the 64KB report_json DB column) —
            # persist it as a workspace file and keep only a compact summary in
            # the report itself.
            wave_json_path = waves_dir / "waveform.json"
            wave_json_path.write_text(json.dumps(wave_json))
            register_artifact(artifacts, path="waves/waveform.json", kind="waveform", stage="SIM", base=workspace)
            report.waveform_summary = {
                "tmax": wave_json.get("tmax", 0),
                "signals": [{"name": s.get("name"), "width": s.get("width")}
                            for s in wave_json.get("signals", [])][:32],
                "trace_path": "waves/waveform.json",
            }
        except _VCDTooBig:
            pass  # already logged; the run's real results are unaffected
        except Exception as exc:  # noqa: BLE001 - waveform parse must never fail the stage
            log.append(f"(waveform parse failed: {exc})")
            report.warnings.append(f"waveform parse failed: {exc}")
        register_artifact(artifacts, path="waves/design.vcd", kind="waveform", stage="SIM", base=workspace)
        # Render the waveform to a PNG so the UI can SHOW the signals toggling
        # (GarudaChip show_waveform); best-effort, never fails the stage.
        if not oversized and vcd.render_png(vcd_path, waves_dir / "waveform.png"):
            log.append("rendered waves/waveform.png")
            register_artifact(artifacts, path="waves/waveform.png", kind="image", stage="SIM", base=workspace)

    # CHIP OUTPUT rendering (GarudaChip inference display): a testbench that
    # $writememh-dumps the chip's RESULT into waves/*.mem gets that data
    # rendered to a PNG so the UI shows what the RTL actually computed.
    from .memimg import render_mem_image, _read_values
    for mem_file in sorted(waves_dir.glob("*.mem")):
        out_png = mem_file.with_suffix(".png")
        if render_mem_image(mem_file, out_png, workspace=workspace):
            rel = f"waves/{out_png.name}"
            log.append(f"rendered chip data {rel} from {mem_file.name}")
            register_artifact(artifacts, path=rel, kind="image", stage="SIM", base=workspace)

    # GOLDEN COMPARISON (python-first verification): the chip is only correct
    # when input → RTL output equals input → golden-model output. Deterministic
    # value-by-value check; any mismatch fails the stage with the diff.
    golden_mem = waves_dir / "golden_output.mem"
    chip_mem = waves_dir / "chip_output.mem"
    golden_match = None
    # GOLDEN INDEPENDENCE gate: a testbench that $writememh-writes the golden
    # file is comparing the chip against its own fabrication — reject it.
    tb_dir = workspace / "tb"
    if tb_dir.is_dir():
        for tb_file in sorted(tb_dir.glob("*.*v")):
            try:
                tb_txt = tb_file.read_text(errors="replace")
            except Exception:  # noqa: BLE001
                continue
            if re.search(r"\$writememh\s*\(\s*\"[^\"]*golden", tb_txt):
                passed = False
                log.append(f"CONTRACT VIOLATION: {tb_file.name} writes waves/golden_output.mem — "
                           "the desired output must come from the Python golden model, never the "
                           "testbench; remove that dump and regenerate the golden with run_python")
                report.errors.append("testbench fabricates golden_output.mem")
                break
    if golden_mem.is_file() and chip_mem.is_file():
        golden_vals = _read_values(golden_mem)
        chip_vals = _read_values(chip_mem)
        diffs = []
        if len(golden_vals) != len(chip_vals):
            diffs.append(f"length mismatch: golden={len(golden_vals)} chip={len(chip_vals)}")
        for i, (gv, cv) in enumerate(zip(golden_vals, chip_vals)):
            if gv != cv:
                diffs.append(f"index {i}: golden=0x{gv:x} chip=0x{cv:x}")
            if len(diffs) >= 12:
                diffs.append("… (more mismatches truncated)")
                break
        if diffs:
            passed = False
            shape = _mismatch_shape(golden_vals, chip_vals, workspace)
            law = _mismatch_law(golden_vals, chip_vals)
            log.append("GOLDEN MISMATCH — chip output differs from the golden model:")
            if shape:
                log.append("  " + shape)
            if law:
                log.append("  " + law)
            log.extend("  " + d for d in diffs)
            # The LAW is the actionable half — carry it into the error the repair
            # stage reads, not just into the log tail it may never quote.
            report.errors.append(
                "chip output != golden output"
                + (f" — {shape}" if shape else f" ({len(diffs)} diff(s) shown)")
                + (f" — {law}" if law else ""))
        else:
            log.append(f"✓ chip output MATCHES the golden model ({len(golden_vals)} values)")
        golden_match = not diffs
        if golden_match and passed is not False:
            _record_verified_rtl(workspace)
    else:
        log.append(
            'no design.vcd produced - add `$dumpfile("design.vcd"); '
            '$dumpvars(0, <tb>);` to your testbench to see a waveform.'
        )
        report.warnings.append("no waveform (design.vcd) produced")

    verdict = ("— testbench PASSED" if passed is True
               else "— testbench FAILED (see the log)" if passed is False
               else "(no explicit TEST PASSED/FAILED verdict printed)")
    report.summary = (
        f"Simulation completed {verdict}" if report.compiled else "Simulation failed"
    ) + (" with waveform." if report.waveform else ".")
    if passed is False:
        report.errors.append("self-checking testbench FAILED")
    report.metrics = {
        "compiled": report.compiled,
        "waveform": report.waveform,
        "passed": passed,
        "golden_match": golden_match,
        "signal_count": len(report.waveform_summary.get("signals", [])) if report.waveform else 0,
    }
    _finalize_log(report, logs_dir, log, artifacts)
    return report


def run_lint(
    workspace: Path,
    sources: List[Path],
    top: str = "",
    opts: Optional[Dict] = None,
    runner: CommandRunner = default_runner,
) -> LintReport:
    """Lint synthesizable RTL with ``iverilog -t null`` (syntax/elaboration check).

    Informative, not fatal: findings are captured as warnings/errors on the
    report rather than raising, mirroring GarudaChip's tolerant lint policy.
    """
    opts = opts or {}
    workspace = Path(workspace)
    rtl_dir = workspace / "rtl"
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    report = LintReport()
    artifacts: List[dict] = []
    vfiles = [Path(p) for p in sources if Path(p).suffix.lower() in COMPILE_EXT]
    report.checked_files = [p.name for p in vfiles]
    log: List[str] = []

    if not vfiles:
        report.summary = "No RTL sources to lint."
        report.clean = True
        _finalize_lint_log(report, logs_dir, log, artifacts)
        return report

    inc = f"-I{rtl_dir}"
    cmd = [_iverilog_bin(), "-g2012", "-t", "null", inc]
    if top:
        cmd += ["-s", top]
    cmd += [str(p) for p in vfiles]
    log.append("$ " + " ".join(["iverilog", "-g2012", "-t", "null", "-I rtl"]
                                + (["-s", top] if top else []) + [p.name for p in vfiles]))
    res = runner.run(cmd, cwd=workspace, timeout=_sim_timeout())
    if res.not_found:
        log.append("iverilog is not installed / not on PATH.")
        report.warnings.append("iverilog not available; lint skipped")
        report.summary = "Lint skipped: iverilog not available."
        _finalize_lint_log(report, logs_dir, log, artifacts)
        return report

    out = res.output
    if out:
        log.append(out)
    if res.returncode != 0:
        report.clean = False
        report.errors.append("lint reported elaboration errors")
        report.summary = "Lint found issues; see log."
    else:
        report.clean = True
        report.summary = "Lint clean."
    # surface warning lines
    for line in out.splitlines():
        if "warning" in line.lower():
            report.warnings.append(line.strip())
    report.metrics = {
        "checked_files": len(vfiles),
        "clean": report.clean,
        "warning_count": len(report.warnings),
    }
    _finalize_lint_log(report, logs_dir, log, artifacts)
    return report


def _finalize_lint_log(report: LintReport, logs_dir: Path, log: List[str], artifacts: List[dict]) -> None:
    log_path = logs_dir / "lint.log"
    log_path.write_text("\n".join(l for l in log if l).strip() + "\n")
    register_artifact(artifacts, path="logs/lint.log", kind="log", stage="LINT", base=logs_dir.parent)
    report.raw_log_paths.append("logs/lint.log")
    report.artifacts = artifacts


def _finalize_log(report: SimReport, logs_dir: Path, log: List[str], artifacts: List[dict]) -> None:
    log_path = logs_dir / "sim.log"
    log_path.write_text("\n".join(l for l in log if l).strip() + "\n")
    workspace = logs_dir.parent
    register_artifact(artifacts, path="logs/sim.log", kind="log", stage="SIM", base=workspace)
    report.raw_log_paths.append("logs/sim.log")
    report.artifacts = artifacts
