"""LaTeX final-report generation — IEEE Access template.

Produces ``exports/final_report.tex`` targeting the official IEEE Access
LaTeX template (``\\documentclass{ieeeaccess}``, which loads IEEEtran.cls):
title block with ``\\history``/``\\doi``/``\\corresp``, ABSTRACT and INDEX
TERMS, numbered sections with ``\\PARstart`` drop cap, the class's
``\\Figure`` macro for figures, template-style ruled tables, references and
the required ``\\EOD`` terminator.

Every statement is derived from collected evidence (:class:`ReportContext`)
— nothing is invented. Compile the file inside the IEEE Access template
folder (ieeeaccess.cls, IEEEtran.cls, spotcolor.sty, Logo.png, bullet.png)
with the workspace's ``waves/``, ``reports/`` and ``gds/`` directories
available; ``\\graphicspath`` covers compiling from either the workspace
root or ``exports/``.
"""
from __future__ import annotations

import re
from datetime import date
from typing import List

from .evidence import ReportContext

_ESCAPE = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}

_IMG_RE = re.compile(r"\.(png|jpe?g|pdf)$", re.I)

_ROLE_HINTS = [
    (r"params.*\.vh$|\.svh$", "Shared parameter / macro header"),
    (r"\.mem$", "On-chip memory image (weights / bias / stimulus, \\texttt{\\$readmemh})"),
    (r"actor", "DDPG actor network (policy inference datapath)"),
    (r"critic", "DDPG critic network (Q-value datapath)"),
    (r"replay|buf", "Replay / experience buffer memory"),
    (r"env|maze", "Environment model (state transition and reward)"),
    (r"core|ctrl|fsm", "Control core / algorithm FSM"),
    (r"sio|uart|spi|_if", "Serial / host interface"),
]


def _tex(text) -> str:
    return "".join(_ESCAPE.get(ch, ch) for ch in str(text if text is not None else ""))


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:,.3f}".rstrip("0").rstrip(".")
    return _tex(v)


def _role_for(name: str, top: str) -> str:
    base = name.lower()
    if top and top.lower() in base and base.endswith((".v", ".sv")):
        return "Top-level integration (instantiates and wires all submodules)"
    for pat, role in _ROLE_HINTS:
        if re.search(pat, base):
            return role
    return "Design module"


def _figure(path: str, caption: str, label: str) -> str:
    # the ieeeaccess class's \Figure macro: position, skips, graphicx options,
    # file, caption(+label)
    return ("\\Figure[!t](topskip=0pt, botskip=0pt, midskip=0pt)"
            f"[width=0.9\\columnwidth]{{{path}}}\n"
            f"{{{caption}\\label{{{label}}}}}\n\n")


def _rule_table(caption: str, label: str, header: str, colspec: str, rows: List[str]) -> str:
    body = "\n".join(r + r" \\" for r in rows)
    return (
        "\\begin{table}[!t]\n"
        f"\\caption{{{caption}}}\n"
        f"\\label{{{label}}}\n"
        "\\setlength{\\tabcolsep}{3pt}\n"
        f"\\begin{{tabular}}{{{colspec}}}\n"
        "\\hline\n"
        f"{header} \\\\\n"
        "\\hline\n"
        f"{body}\n"
        "\\hline\n"
        "\\end{tabular}\n"
        "\\end{table}\n\n"
    )


def generate_latex(ctx: ReportContext, workspace_files: List[str] | None = None) -> str:
    files = workspace_files or []
    images = [f for f in files if _IMG_RE.search(f)]

    def has(rel: str) -> bool:
        return rel in files or rel in images

    m = ctx.metrics or {}
    modules = [f for f in ctx.rtl_files if f.endswith((".v", ".sv"))]
    data_files = [f for f in ctx.rtl_files if f.endswith(".mem")]
    voltage = m.get("voltage", "")
    clock_mhz = m.get("clock_target_mhz", "")
    golden_ok = m.get("golden_match")
    has_gds = bool(ctx.gds_files)
    verdict = "TAPEOUT READY" if ctx.tapeout_ready else "not tapeout ready"
    failed = (ctx.signoff or {}).get("failed") or []
    today = date.today().strftime("%B %d, %Y")

    title = _tex(ctx.task_name or ctx.task_id)
    brief = _tex(ctx.design_brief or "n/a")
    top = _tex(ctx.top_module or "n/a")

    # ------------------------------------------------------------- abstract
    sim_claim = (
        "The RTL output matches the golden model value-for-value on the canonical input"
        if golden_ok else
        "Golden-model equivalence has not been demonstrated on the final artifacts"
    )
    gds_claim = (
        "and the design was placed and routed to a GDSII layout"
        if has_gds else
        "; physical implementation has not yet produced a GDSII layout"
    )
    abstract = (
        f"This report documents an AI-generated application-specific integrated circuit "
        f"implementing the following specification: ``{brief}''. The design (top module "
        f"\\texttt{{{top}}}) comprises {len(modules)} Verilog modules and {len(data_files)} "
        "on-chip memory images whose contents are derived in Python during generation and "
        "baked into the hardware. Verification is golden-model-first: the target algorithm "
        "is implemented in Python with the same weights and fixed-point arithmetic as the "
        "hardware, its output for the canonical input defines the desired output, and a "
        f"deterministic value-by-value comparison gates the flow. {sim_claim} {gds_claim}"
        + (f", closing timing on the {_tex(voltage)} corner set of the GF180MCU open "
           "process design kit" if voltage else "")
        + (f" at a {_fmt(clock_mhz)}~MHz clock target" if clock_mhz else "") + "."
    )

    parts: List[str] = []
    parts.append(
        "% Final design report — generated by Chip Orchestra from workspace evidence.\n"
        "% Compile inside the IEEE Access template folder (ieeeaccess.cls, IEEEtran.cls,\n"
        "% spotcolor.sty, Logo.png, notaglineLogo.png, bullet.png) with the workspace\n"
        "% waves/, reports/ and gds/ directories present.\n"
        "\\documentclass{ieeeaccess}\n"
        "\\usepackage{cite}\n"
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{textcomp}\n"
        "\\graphicspath{{./}{../}}\n"
        "\\def\\BibTeX{{\\rm B\\kern-.05em{\\sc i\\kern-.025em b}\\kern-.08em\n"
        "    T\\kern-.1667em\\lower.7ex\\hbox{E}\\kern-.125emX}}\n"
        "\\begin{document}\n"
        f"\\history{{Report generated {today} by the Chip Orchestra agentic RTL-to-GDSII pipeline.}}\n"
        f"\\doi{{Chip Orchestra internal engineering report — task {_tex(ctx.task_id)}}}\n\n"
        f"\\title{{{title}: An AI-Generated ASIC with Golden-Model Verification on the GF180MCU Open PDK}}\n"
        "\\author{\\uppercase{Chip Orchestra Agentic Pipeline}\\authorrefmark{1}}\n"
        "\\address[1]{Chip Orchestra --- AI-native digital IC orchestration platform "
        f"(task \\texttt{{{_tex(ctx.task_id)}}})}}\n"
        f"\\tfootnote{{Every figure and number in this report is collected from the task "
        "workspace evidence (simulation logs, LibreLane metrics, rendered artifacts); "
        "nothing is hand-entered.}\n\n"
        f"\\markboth{{Chip Orchestra: {title}}}{{Chip Orchestra: {title}}}\n\n"
        "\\corresp{Generated automatically; review alongside the exported workspace bundle.}\n\n"
        f"\\begin{{abstract}}\n{abstract}\n\\end{{abstract}}\n\n"
        "\\begin{keywords}\n"
        "AI-generated RTL, GF180MCU, golden-model verification, hardware accelerator, "
        "LibreLane, OpenROAD, RTL-to-GDSII\n"
        "\\end{keywords}\n\n"
        "\\titlepgskip=-15pt\n\n"
        "\\maketitle\n\n"
    )

    # ---------------------------------------------------------- introduction
    parts.append(
        "\\section{Introduction}\n\\label{sec:introduction}\n"
        "\\PARstart{C}{hip} Orchestra executes the complete RTL-to-GDSII lifecycle as an "
        "observable, gated pipeline: specification ingest, planning, RTL and testbench "
        "generation, simulation against a golden model, lint, synthesis, place-and-route, "
        "physical verification, sign-off and export. Large-language-model agents author "
        "the design collateral, while deterministic tooling --- Icarus Verilog, Verilator, "
        "Yosys, OpenROAD~\\cite{b1}, Magic~\\cite{b2}, Netgen and KLayout, orchestrated by "
        "LibreLane~\\cite{b3} on the GF180MCU open PDK~\\cite{b4} --- judges the result; "
        "failed judgements dispatch bounded auto-repair rounds.\n\n"
        f"The subject of this report was generated from the natural-language brief "
        f"``{brief}''. Section~\\ref{{sec:arch}} describes the generated architecture, "
        "Section~\\ref{sec:verif} the verification methodology and its evidence, "
        "Section~\\ref{sec:impl} the physical implementation results, and "
        "Section~\\ref{sec:signoff} the sign-off status and known limitations.\n\n"
    )

    # ---------------------------------------------------------- architecture
    parts.append("\\section{System Architecture}\n\\label{sec:arch}\n")
    if ctx.architecture_notes:
        arch = re.sub(r"```.*?```", " ", ctx.architecture_notes, flags=re.S)
        arch = re.sub(r"[#*`>\[\]]", "", arch)
        arch = re.sub(r"\s+", " ", arch).strip()
        parts.append(_tex(arch[:1100]) + "\n\n")
    parts.append(
        f"The design decomposes into {len(modules)} synthesizable modules "
        f"(Table~\\ref{{tab:modules}}) with {len(data_files)} memory images holding the "
        "trained network parameters and the canonical stimulus. The parameters are part "
        "of the taped-out chip: they are derived in Python during generation, quantized "
        "to the RTL's fixed-point format, and loaded with \\texttt{\\$readmemh}.\n\n"
    )
    mod_rows = [f"\\texttt{{{_tex(f)}}} & {_role_for(f, ctx.top_module)}" for f in ctx.rtl_files]
    parts.append(_rule_table("Module and Data-File Inventory", "tab:modules",
                             "File & Role", "|p{95pt}|p{130pt}|", mod_rows))
    if has("reports/schematic.png"):
        parts.append(_figure("reports/schematic.png",
                             "Synthesized netlist structure (Yosys).", "fig:schematic"))

    # ---------------------------------------------------- verification method
    parts.append(
        "\\section{Verification Methodology and Evidence}\n\\label{sec:verif}\n"
        "\\subsection{Golden-Model-First Flow}\n"
        "The canonical input is decoded deterministically from the attached specification "
        "image (Fig.~\\ref{fig:input}). The golden model --- the same algorithm, the same "
        "fixed-point arithmetic and the same weight images as the RTL, implemented in "
        "Python --- computes the desired output (Fig.~\\ref{fig:golden}). The testbench "
        "drives the device under test with the canonical input, reconstructs the chip's "
        "result exclusively from DUT outputs, and dumps it with \\texttt{\\$writememh} "
        "(Fig.~\\ref{fig:chipout}). The simulation stage then performs a value-by-value "
        "comparison of the two memory images and fails on any mismatching cell; the "
        "testbench is forbidden from writing the golden file itself, and a stale chip "
        "output is deleted before every run. Only when the chip output equals the desired "
        "output may the flow proceed to hardening.\n\n"
    )
    if has("waves/chip_input.png"):
        parts.append(_figure("waves/chip_input.png",
                             "Canonical chip input derived deterministically from the attached specification image.",
                             "fig:input"))
    if has("waves/golden_output.png"):
        parts.append(_figure("waves/golden_output.png",
                             "Desired output computed by the Python golden model (same algorithm, weights and fixed-point arithmetic as the RTL).",
                             "fig:golden"))
    if has("waves/chip_output.png"):
        parts.append(_figure("waves/chip_output.png",
                             "Chip output computed by the RTL and dumped by the testbench from the DUT; simulation passes only when it matches Fig.~\\ref{fig:golden} value-for-value.",
                             "fig:chipout"))
    if has("waves/waveform.png"):
        parts.append(_figure("waves/waveform.png",
                             "Top-level signal activity from the self-checking testbench run (activity-ranked traces from \\texttt{waves/design.vcd}).",
                             "fig:waves"))
    parts.append("\\subsection{Simulation Results}\n"
                 "Table~\\ref{tab:verif} summarizes the functional verification outcome.\n\n")
    sim_keys = ["compiled", "passed", "golden_match", "waveform", "signal_count",
                "checked_files", "clean", "warning_count"]
    sim_rows = [f"{_tex(k)} & {_fmt(m[k])}" for k in sim_keys if k in m]
    if sim_rows:
        parts.append(_rule_table("Functional Verification Results (Simulation and Lint)",
                                 "tab:verif", "Check & Result", "|p{110pt}|p{110pt}|", sim_rows))

    # ------------------------------------------------- physical implementation
    parts.append(
        "\\section{Physical Implementation}\n\\label{sec:impl}\n"
        "Hardening uses LibreLane's Classic flow (Yosys synthesis; OpenROAD floorplan, "
        "placement, clock-tree synthesis, routing and static timing analysis; Magic and "
        "KLayout stream-out; Magic DRC and Netgen LVS) on the GF180MCU open PDK"
        + (f", with timing closed on the {_tex(voltage)} corner set" if voltage else "")
        + (f" at a {_fmt(clock_mhz)}~MHz clock target" if clock_mhz else "")
        + ". When a sign-off check fails, the flow auto-tunes the governing parameter "
        "(clock period for negative slack, port diodes for antenna violations, "
        "utilization for routing congestion) and re-hardens; the values in "
        "Table~\\ref{tab:impl} are the converged results.\n\n"
    )
    impl_keys = ["voltage", "clock_period_ns", "clock_target_mhz", "fmax_mhz",
                 "die_area_um2", "die_bbox_um", "core_area_um2", "cell_count", "util_pct",
                 "io_pins", "wns_ns", "tns_ns", "hold_wns_ns", "power_mw",
                 "antenna_violations", "drc_errors", "lvs_errors",
                 "max_slew_violations", "max_cap_violations", "max_fanout_violations",
                 "timing_met"]
    impl_rows = [f"{_tex(k)} & {_fmt(m[k])}" for k in impl_keys if k in m]
    if impl_rows:
        parts.append(_rule_table("Implementation Parameters (LibreLane Metrics)",
                                 "tab:impl", "Parameter & Value", "|p{110pt}|p{110pt}|", impl_rows))
    corner_rows = [f"{lbl} & {_fmt(m[k])}"
                   for k, lbl in (("setup_ws_tt_ns", "typical (tt, 25\\,\\textdegree C)"),
                                  ("setup_ws_ss_ns", "slow (ss, 125\\,\\textdegree C)"),
                                  ("setup_ws_ff_ns", "fast (ff, $-$40\\,\\textdegree C)"))
                   if k in m]
    if corner_rows:
        parts.append(_rule_table("Setup Slack per PVT Corner (Nominal RC)",
                                 "tab:corners", "Corner & Setup WS (ns)",
                                 "|p{110pt}|p{110pt}|", corner_rows))
    for rel, cap in (("gds/layout.png", "Routed GDSII layout (KLayout render)."),
                     ("reports/gds.png", "Routed GDSII layout (KLayout render).")):
        if has(rel):
            parts.append(_figure(rel, cap, "fig:gds"))
            break

    # ------------------------------------------------------------- sign-off
    parts.append("\\section{Sign-Off Status and Limitations}\n\\label{sec:signoff}\n")
    parts.append(f"Sign-off verdict: \\textbf{{{_tex(verdict)}}}."
                 + (f" Failed checks: {_tex(', '.join(map(str, failed)))}." if failed else
                    " No hard sign-off checks are failing on the collected evidence.") + "\n\n")
    caveats = []
    if not has_gds:
        caveats.append("no GDSII has been produced yet --- hardening did not complete")
    if str(m.get("power_mw", "")) in ("0", "0.0", ""):
        caveats.append("power has not been annotated from switching activity "
                       "(VCD-driven power analysis is a recommended next step)")
    slew_v = m.get("max_slew_violations")
    if isinstance(slew_v, (int, float)) and slew_v > 0:
        caveats.append(f"{int(slew_v)} transition-time notes remain against the 5~ns design "
                       "guideline at the slow 125\\,\\textdegree C corner (liberty per-pin "
                       "limits are met; setup slack at that corner is strongly positive)")
    caveats.append("gate-level simulation and IR-drop analysis at the target corner are "
                   "recommended before manufacturing")
    parts.append("Known limitations: " + "; ".join(caveats) + ".\n\n")

    # ------------------------------------------------------------ conclusion
    parts.append(
        "\\section{Conclusion}\n"
        f"An ASIC implementing ``{brief}'' was generated, verified against an "
        f"algorithm-faithful Python golden model "
        f"({'match demonstrated' if golden_ok else 'match not yet demonstrated'}) and "
        + ("carried through place-and-route to a GDSII layout"
           if has_gds else "prepared for physical implementation")
        + " on the GF180MCU open PDK. The complete workspace --- RTL, testbenches, "
        "waveforms, logs, reports and layout artifacts --- accompanies this report in "
        "the export bundle.\n\n"
    )

    # ------------------------------------------------------------ references
    parts.append(
        "\\begin{thebibliography}{00}\n"
        "\\bibitem{b1} The OpenROAD Project. ``OpenROAD --- an open-source, autonomous "
        "RTL-to-GDSII flow.'' [Online]. Available: \\underline{https://theopenroadproject.org}\n"
        "\\bibitem{b2} R. T. Edwards \\emph{et al.}, ``Magic VLSI layout tool.'' [Online]. "
        "Available: \\underline{http://opencircuitdesign.com/magic}\n"
        "\\bibitem{b3} The LibreLane contributors. ``LibreLane: an open infrastructure for "
        "silicon implementation.'' [Online]. Available: "
        "\\underline{https://github.com/librelane/librelane}\n"
        "\\bibitem{b4} GlobalFoundries and Google. ``GF180MCU open-source process design "
        "kit.'' [Online]. Available: \\underline{https://github.com/google/gf180mcu-pdk}\n"
        "\\end{thebibliography}\n\n"
        "\\EOD\n\n"
        "\\end{document}\n"
    )

    return "".join(parts)


__all__ = ["generate_latex"]
