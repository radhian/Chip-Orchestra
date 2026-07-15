"""LaTeX final-report generation — the full design story, spec → GDS.

Produces ``exports/final_report.tex``: overview, the attached spec images, the
IP/module inventory, verification evidence (testbenches, sim verdict, waveform
figure, chip input/output figures), the LibreLane implementation parameters
(WNS/TNS, power, die size, utilization, antenna/DRC/LVS counts, IO pins), the
GDS render, and the signoff verdict. Images are referenced workspace-relative
via ``\\graphicspath``, so ``pdflatex exports/final_report.tex`` compiles from
the workspace root.
"""
from __future__ import annotations

import re
from typing import List

from .evidence import ReportContext

_ESCAPE = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def _tex(text) -> str:
    return "".join(_ESCAPE.get(ch, ch) for ch in str(text if text is not None else ""))


def _figure(path: str, caption: str) -> str:
    return (
        "\\begin{figure}[H]\n\\centering\n"
        f"\\includegraphics[width=0.82\\linewidth]{{{path}}}\n"
        f"\\caption{{{_tex(caption)}}}\n\\end{{figure}}\n"
    )


def _metric_rows(metrics: dict) -> str:
    rows = []
    for key in sorted(metrics):
        rows.append(f"{_tex(key)} & {_tex(metrics[key])} \\\\")
    return "\n".join(rows)


_IMG_RE = re.compile(r"\.(png|jpe?g|pdf)$", re.I)


def generate_latex(ctx: ReportContext, workspace_files: List[str] | None = None) -> str:
    """Render the complete LaTeX report from the collected evidence."""
    files = workspace_files or []
    images = [f for f in files if _IMG_RE.search(f)]
    uploads = [f for f in images if f.startswith("context/uploads/")]
    waveform = [f for f in images if "waveform" in f.lower()]
    chip_in = [f for f in images if "input" in f.lower() and f not in uploads]
    chip_out = [f for f in images if ("output" in f.lower() or "result" in f.lower())
                and f not in waveform]
    gds_imgs = ([f for f in ctx.gds_files if _IMG_RE.search(f)]
                + [f for f in images if f in ("reports/gds.png",) or f.startswith("gds/")])
    gds_imgs = list(dict.fromkeys(gds_imgs))
    schematic = [f for f in images if "schematic" in f.lower()]

    rtl = sorted(ctx.rtl_files)
    tbs = sorted(ctx.tb_files)
    metrics = dict(ctx.metrics or {})
    failed = (ctx.signoff or {}).get("failed", [])

    parts: List[str] = []
    parts.append(
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[margin=2.4cm]{geometry}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{float}\n"
        "\\usepackage{longtable}\n"
        "\\usepackage{booktabs}\n"
        "\\usepackage{hyperref}\n"
        "\\graphicspath{{../}{./}}\n"
        f"\\title{{Design Report --- {_tex(ctx.task_name or ctx.task_id)}}}\n"
        "\\author{Chip Orchestra (AI-generated design flow)}\n"
        "\\date{\\today}\n"
        "\\begin{document}\n\\maketitle\n\\tableofcontents\n\\newpage\n"
    )

    parts.append("\\section{Overview}\n" + _tex(ctx.design_brief or "(no brief)") + "\n")
    parts.append(f"\\noindent Top module: \\texttt{{{_tex(ctx.top_module)}}}. "
                 f"Tapeout ready: {'yes' if ctx.tapeout_ready else 'no'}.\n")
    for img in uploads[:3]:
        parts.append(_figure(img, "User-attached specification image (read by the vision model)."))

    parts.append("\\section{Architecture and IP Inventory}\n")
    if rtl:
        parts.append("The design decomposes into the following RTL files (one IP/module per file):\n"
                     "\\begin{longtable}{ll}\n\\toprule\nFile & Role \\\\\n\\midrule\n")
        for f in rtl:
            role = "shared header" if f.endswith((".vh", ".svh")) else (
                "data/LUT image" if f.endswith(".mem") else "RTL module")
            parts.append(f"\\texttt{{{_tex(f)}}} & {role} \\\\")
        parts.append("\\bottomrule\n\\end{longtable}\n")
    else:
        parts.append("(no RTL files recorded)\n")
    if ctx.architecture_notes:
        parts.append(_tex(ctx.architecture_notes[:2500]) + "\n")
    for img in schematic[:1]:
        parts.append(_figure(img, "Synthesized netlist schematic."))

    parts.append("\\section{Verification}\n")
    if tbs:
        parts.append("Self-checking testbenches:\n\\begin{itemize}\n"
                     + "\n".join(f"\\item \\texttt{{{_tex(t)}}}" for t in tbs)
                     + "\n\\end{itemize}\n")
    sim = ctx.simulation or {}
    if sim:
        parts.append(f"Simulation: {_tex(sim.get('summary', ''))}\n")
    for img in waveform[:2]:
        parts.append(_figure(img, "Simulation waveform (from waves/design.vcd)."))
    if chip_in or chip_out:
        parts.append("\\subsection{Chip input / output}\n"
                     "The stimulus below was generated programmatically and driven into the "
                     "DUT; the output figure is rendered from the values the RTL computed "
                     "(testbench \\texttt{\\$writememh} dump).\n")
        for img in chip_in[:2]:
            parts.append(_figure(img, "Chip input stimulus."))
        for img in chip_out[:2]:
            parts.append(_figure(img, "Chip output (computed by the RTL)."))

    parts.append("\\section{Implementation (LibreLane)}\n")
    if metrics:
        parts.append("\\begin{longtable}{ll}\n\\toprule\nParameter & Value \\\\\n\\midrule\n"
                     + _metric_rows(metrics)
                     + "\n\\bottomrule\n\\end{longtable}\n")
    else:
        parts.append("(no implementation metrics recorded yet)\n")
    for img in gds_imgs[:2]:
        parts.append(_figure(img, "Hardened GDS layout render."))

    parts.append("\\section{Signoff}\n")
    parts.append(f"Failed checks: {_tex(', '.join(failed) if failed else 'none')}. "
                 f"Tapeout ready: {'yes' if ctx.tapeout_ready else 'no'}.\n")
    if ctx.gds_files:
        parts.append("Deliverables:\n\\begin{itemize}\n"
                     + "\n".join(f"\\item \\texttt{{{_tex(g)}}}" for g in sorted(ctx.gds_files)[:10])
                     + "\n\\end{itemize}\n")

    parts.append("\\end{document}\n")
    return "\n".join(parts)


__all__ = ["generate_latex"]
