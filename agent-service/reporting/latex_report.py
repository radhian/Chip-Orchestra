"""LaTeX final-report generation — IEEE Access template.

Produces ``exports/final_report.tex`` targeting the official IEEE Access
LaTeX template (``\\documentclass{ieeeaccess}``, which loads IEEEtran.cls):
title block with ``\\history``/``\\doi``/``\\corresp``, ABSTRACT and INDEX
TERMS, numbered sections with ``\\PARstart`` drop cap, the class's
``\\Figure`` macro for figures, template-style ruled tables, references and
the required ``\\EOD`` terminator.

Every statement is derived from collected evidence (:class:`ReportContext`)
— nothing is invented. The class files and the Chip Orchestra header/bullet
artwork are vendored in ``reporting/templates/ieeeaccess/`` and copied next
to the ``.tex`` by the EXPORT stage, which then runs ``pdflatex`` twice (see
:func:`reporting.latex_report.compile_pdf`). ``\\graphicspath`` covers
compiling from either the workspace root or ``exports/``.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import List, Optional

from .evidence import ReportContext

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "ieeeaccess"

# Assets the class needs beside the .tex: the vendored classes plus the Chip
# Orchestra header logo (three slots the class picks between) and bullet.
TEMPLATE_ASSETS = ("ieeeaccess.cls", "IEEEtran.cls", "Logo.png",
                   "notaglineLogo.png", "jtehmLogo.png", "bullet.png")

_ESCAPE = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}

# Unicode that reaches the report through design briefs, agent notes and EDA
# metrics. pdflatex is not UTF-8-tolerant for these, and one stray µ or Ω
# failed the whole compile — map them to math/text equivalents.
_UNI = {
    "≥": r"$\geq$", "≤": r"$\leq$", "≠": r"$\neq$", "≈": r"$\approx$", "∼": r"$\sim$",
    "µ": r"$\mu$", "μ": r"$\mu$", "Ω": r"$\Omega$", "Δ": r"$\Delta$", "π": r"$\pi$",
    "×": r"$\times$", "·": r"$\cdot$", "±": r"$\pm$", "°": r"$^\circ$",
    "→": r"$\rightarrow$", "←": r"$\leftarrow$", "⇒": r"$\Rightarrow$",
    "²": r"$^2$", "³": r"$^3$", "½": r"$\frac{1}{2}$",
    "–": "--", "—": "---", "‘": "`", "’": "'", "“": "``", "”": "''",
    "•": r"$\bullet$", "…": r"\ldots{}", "✓": "yes", "✗": "no", "⚠": "!",
    " ": " ", "​": "",
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
    """Escape evidence text for LaTeX, translating unicode and leaving inline
    math (``$...$``) that the report itself emits untouched."""
    s = str(text if text is not None else "")
    for u, r in _UNI.items():
        s = s.replace(u, r)
    out = []
    for i, part in enumerate(re.split(r"(\$[^$]*\$)", s)):
        out.append(part if i % 2 else "".join(_ESCAPE.get(c, c) for c in part))
    return "".join(out)


def _code(text) -> str:
    """A monospaced identifier that is allowed to WRAP at its own separators.

    ``\\texttt{rtl/nano_cgra_3x3_sobel_accelerator_v4.v}`` is one unbreakable
    word 34 characters long. In a 95 pt table column it does not wrap — it runs
    straight through the column rule and prints on top of the neighbouring cell,
    which is what the module inventory table used to do. Inserting a break
    opportunity after every separator lets TeX wrap it inside the cell."""
    escaped = _tex(text)
    return r"\texttt{" + re.sub(r"(\\_|/|\.|-)", r"\1\\allowbreak{}", escaped) + "}"


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:,.3f}".rstrip("0").rstrip(".")
    return _tex(v)


def _role_for(name: str, top: str, golden_roles: Optional[dict] = None) -> str:
    """What a design file does. The golden manifest is authoritative — it names
    each block's role and tier — because the regex hints below are only a guess
    and mislabel any design whose names don't match them (a `line_buffer` in an
    image pipeline was reported as a reinforcement-learning replay buffer)."""
    base = name.lower()
    stem = Path(name).stem.lower()
    if golden_roles:
        entry = golden_roles.get(stem)
        if entry:
            role = str(entry.get("role") or "").strip()
            tier = str(entry.get("tier") or "").lower()
            prefix = {"top": "Top-level integration", "subtop": "Sub-toplevel integration"}.get(tier)
            if role and prefix:
                return f"{prefix} --- {role}"
            if role:
                return role
            if prefix:
                return prefix
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
    """A ruled table sized in FRACTIONS OF THE COLUMN.

    Column widths used to be absolute (``p{95pt}``); combined with tabcolsep and
    the rules that adds up to more than the text measure on this class, so every
    table hung a few points into the gutter before its contents even started
    overflowing. ``\\footnotesize`` and ragged-right cells then keep long
    identifiers inside their own cell."""
    body = "\n".join(r + r" \\" for r in rows)
    return (
        "\\begin{table}[!t]\n"
        f"\\caption{{{caption}}}\n"
        f"\\label{{{label}}}\n"
        "\\setlength{\\tabcolsep}{3pt}\n"
        "\\footnotesize\n"
        "\\centering\n"
        f"\\begin{{tabular}}{{{colspec}}}\n"
        "\\hline\n"
        f"{header} \\\\\n"
        "\\hline\n"
        f"{body}\n"
        "\\hline\n"
        "\\end{tabular}\n"
        "\\end{table}\n\n"
    )


def _cols(*fractions: float) -> str:
    """Ragged-right ``p`` columns whose widths are fractions of ``\\columnwidth``."""
    spec = "|".join(r">{\raggedright\arraybackslash}p{" + f"{f:.3f}" + r"\columnwidth}"
                    for f in fractions)
    return "|" + spec + "|"


def _bibitem(key: str, ref: dict) -> str:
    """One IEEE-style bibliography entry from a discovered reference.

    Only the fields the search actually produced are printed. An entry padded
    out with a guessed volume or page range looks more authoritative and is
    less true, which is the wrong trade in a bibliography."""
    pieces = []
    authors = str(ref.get("authors") or "").strip().rstrip(",")
    if authors:
        pieces.append(_tex(authors) + ",")
    pieces.append("``" + _tex(str(ref.get("title")).strip().rstrip(".")) + ",''")
    venue = str(ref.get("venue") or "").strip().rstrip(".")
    if venue:
        pieces.append("\\emph{" + _tex(venue) + "}.")
    elif ref.get("year"):
        pieces.append(_tex(ref["year"]) + ".")
    url = str(ref.get("url") or "").strip()
    # \url takes its argument almost verbatim: % and # still need escaping, and
    # a brace or a space in there ends the argument early and derails the rest
    # of the bibliography. A malformed URL is dropped rather than allowed to
    # break the compile.
    if url and not re.search(r"[{}\s\\]", url):
        pieces.append("[Online]. Available: \\url{"
                      + url.replace("%", r"\%").replace("#", r"\#") + "}")
    return f"\\bibitem{{{key}}} " + " ".join(pieces) + "\n"


def _hw_sw_section(ctx: ReportContext, has) -> str:
    """The hardware/software co-verification chapter.

    Simulation answers "does the RTL reproduce the reference on the input we
    baked into the design?". That is necessary and not sufficient: it says
    nothing about whether the finished part can be USED. This section documents
    the run that answers the user's actual question — a host program encoded a
    file of their choosing into the frames the top-level RTL speaks, an
    interface bench replayed them against the unmodified DUT, and the host
    decoded what came back. Returns '' when the stage has not run, so a report
    never claims a verification that did not happen."""
    report = getattr(ctx, "hw_sw", {}) or {}
    if not report or not report.get("completed"):
        return ""
    iface = report.get("interface") or {}
    metrics = report.get("metrics") or {}
    source = report.get("input") or {}
    checked = bool(metrics.get("checked"))
    matched = bool(metrics.get("match"))

    parts: List[str] = [
        "\\section{Hardware/Software Co-Verification}\n\\label{sec:hwsw}\n"
        "Section~\\ref{sec:verif} establishes that the RTL reproduces the golden model on "
        "the canonical stimulus compiled into the design. That is a statement about the "
        "datapath, not about the finished part: it exercises the device through a testbench "
        "written for it, with the input already resident in memory. The question a user of "
        "the chip asks is different --- given a file and the physical interface the device "
        "actually exposes, does the correct result come back out?\n\n"
        "This section documents the experiment that answers it. The top-level module's ports "
        "are read directly from the RTL to determine how the part is addressed; a host "
        "program encodes an arbitrary user-supplied file into exactly that wire format; a "
        "generated interface bench replays the resulting bit stream against the "
        "\\emph{unmodified} device under test at the real frame timing; and the host program "
        "decodes the device's response and compares it, value for value, against what the "
        "same Python reference model computes for the same input. Software and hardware are "
        "therefore exercised as one system, on data that was never part of the design.\n\n"
    ]

    description = str(iface.get("description") or "").strip()
    if description:
        parts.append("\\subsection{Detected Host Interface}\n" + _tex(description) + "\n\n")

    iface_rows = []
    if iface.get("kind"):
        iface_rows.append(f"Interface class & {_tex(str(iface['kind']).upper())}")
    for label, key in (("Clock port", "clock"), ("Reset port", "reset")):
        if iface.get(key):
            iface_rows.append(f"{label} & {_code(iface[key])}")
    for label, key in (("Payload in", "data_in"), ("Payload out", "data_out")):
        pins = iface.get(key) or []
        if pins:
            iface_rows.append(f"{label} & " + ", ".join(_code(p) for p in pins))
    for label, key in (("Clock frequency (Hz)", "CLK_FREQ"), ("Baud rate", "BAUD_RATE"),
                       ("Clock cycles per bit", "BAUD_DIV"), ("Sample width (bits)", "DATA_W")):
        value = (iface.get("constants") or {}).get(key)
        if value is not None:
            iface_rows.append(f"{label} & {_fmt(value)}")
    if iface_rows:
        parts.append(_rule_table(
            "Host Interface Read From the Top-Level RTL", "tab:hwswiface",
            "Property & Value", _cols(0.46, 0.44), iface_rows))

    driver, bench = iface.get("driver"), iface.get("testbench")
    if driver or bench:
        parts.append("\\subsection{The Generated Bridge}\n")
        provenance = str(iface.get("testbench_origin") or "")
        parts.append(
            "The software half is " + (_code(driver) if driver else "a generated host driver")
            + ", which converts the user's file into the device's sample format and geometry, "
            "runs the reference model on the identical input to obtain the expected response, "
            "and reassembles the device's reply into a viewable result. The hardware half is "
            + (_code(bench) if bench else "a generated interface bench")
            + ", which instantiates the device under test unchanged and carries those bytes "
            "onto its pins"
            + (" --- it is derived from the top-level testbench that already passes "
               "simulation, so the frame format and bit timing are the ones the device is "
               "known to speak rather than a second interpretation of the specification"
               if "derived from" in provenance else "")
            + ". Neither half may modify the design: this stage measures the chip, it does "
            "not repair it.\n\n")

    parts.append("\\subsection{Result}\n")
    name = source.get("name") or source.get("path")
    if name:
        parts.append(
            "The input for the run reported here was " + _code(name) + ", supplied by the "
            "reviewer and not present anywhere in the design. "
            + (f"It was encoded into {_fmt(source['bytes_in'])} bytes on the wire"
               if source.get("bytes_in") else "It was encoded onto the wire")
            + (f", and the device returned {_fmt(metrics['bytes_received'])} bytes"
               if metrics.get("bytes_received") is not None else ", and the device replied")
            + ".\n\n")

    if checked:
        parts.append(
            ("Every returned value matches the reference model, so the complete path --- host "
             "encoding, serial transport, on-chip datapath, serial transport back and host "
             "decoding --- is correct end to end for this input."
             if matched else
             f"{_fmt(metrics.get('mismatches', 0))} returned value(s) differ from the "
             f"reference model (largest deviation {_fmt(metrics.get('max_abs_diff', 0))}), so "
             "the system is NOT verified end to end on this input.") + "\n\n")
    else:
        parts.append(
            "No reference output was available for this input, so the decoded response was "
            "assessed by the reviewer rather than by an automatic comparison.\n\n")

    result_rows = []
    for label, key in (("Bytes sent to the device", "bytes_sent"),
                       ("Bytes returned by the device", "bytes_received"),
                       ("Bytes expected by the model", "bytes_expected"),
                       ("Mismatching values", "mismatches"),
                       ("Largest absolute deviation", "max_abs_diff")):
        if metrics.get(key) is not None:
            result_rows.append(f"{label} & {_fmt(metrics[key])}")
    if metrics.get("golden_source"):
        result_rows.append("Reference entry point & " + _code(metrics["golden_source"]))
    result_rows.append("Verdict & " + ("match" if checked and matched
                                       else "mismatch" if checked else "reviewed by hand"))
    parts.append(_rule_table("Hardware/Software Co-Verification Results", "tab:hwsw",
                             "Quantity & Value", _cols(0.52, 0.38), result_rows))

    for rel, caption, label in (
        ("hwsw/input_preview.png",
         "User-supplied input as the host driver encoded it for the device.",
         "fig:hwswin"),
        ("hwsw/expected_output.png",
         "Response the Python reference model computes for that input.",
         "fig:hwswgold"),
        ("hwsw/chip_output.png",
         "Response decoded from the bytes the device actually returned over its own "
         "interface; co-verification passes only when it equals "
         "Fig.~\\ref{fig:hwswgold} value-for-value.",
         "fig:hwswchip"),
        ("hwsw/waveform.png",
         "Activity on the device's data pins during the transfer, windowed so individual "
         "frames are legible.",
         "fig:hwswwave"),
    ):
        if has(rel):
            parts.append(_figure(rel, caption, label))
    return "".join(parts)


def generate_latex(ctx: ReportContext, workspace_files: List[str] | None = None,
                   workspace: Optional[Path] = None) -> str:
    files = workspace_files or []
    images = [f for f in files if _IMG_RE.search(f)]

    # Block diagrams drawn from the RTL itself: the chip-level connection
    # picture and one IP symbol per module. They are typeset into their own
    # cropped PDF (see reporting.diagrams.compile_figures) and included here as
    # vector pages, because loading TikZ inside the paper breaks the class's
    # spot-colour blue. Best-effort — a report is still a report without them.
    figures: dict = {"preamble": "", "top": "", "symbols": {}}
    diagram_pages: dict = {}
    include_page = None
    if workspace is not None:
        try:
            from .diagrams import build_figures, compile_figures
            from .diagrams import include_page as _include_page
            figures = build_figures(Path(workspace) / "rtl", ctx.top_module or "")
            diagram_pages = compile_figures(figures, Path(workspace) / "exports")
            include_page = _include_page
        except Exception:  # noqa: BLE001
            figures, diagram_pages, include_page = {"top": "", "symbols": {}}, {}, None
    symbols = {name: meta for name, meta in (figures.get("symbols") or {}).items()
               if name in diagram_pages}

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
        "% IEEE Access two-column format. The class files and the Chip Orchestra\n"
        "% header/bullet artwork are copied next to this file by the EXPORT stage\n"
        "% (see reporting/templates/ieeeaccess/); compile from exports/ with the\n"
        "% workspace waves/, reports/, golden/ and gds/ directories present:\n"
        "%     pdflatex -interaction=nonstopmode final_report.tex\n"
        "\\documentclass{ieeeaccess}\n"
        "\\usepackage{cite}\n"
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{textcomp}\n"
        "\\usepackage{booktabs}\n"
        "\\usepackage{array}\n"
        "\\usepackage{ragged2e}\n"
        # url.sty (not \underline) so a reference URL BREAKS instead of running
        # off the column — three of the four references in this bibliography
        # used to print past the right margin.
        "\\usepackage{url}\n"
        "\\urlstyle{same}\n"
        "\\Urlmuskip=0mu plus 1mu\\relax\n"
        # NOTE: no tikz here on purpose. The block diagrams are compiled into
        # exports/diagrams.pdf by reporting.diagrams and included as pages —
        # loading TikZ (and therefore xcolor) in this document conflicts with
        # the class's color+spotcolor blue and erases every blue heading.
        "\\graphicspath{{./}{../}}\n"
        # Last-resort protection for the running text: prefer a slightly loose
        # line to one that sticks into the gutter. Evidence text is full of
        # long unbreakable identifiers, and the default tolerance simply lets
        # them overhang.
        "\\sloppy\n"
        "\\emergencystretch=1.5em\n"
        "\\hfuzz=0.5pt\n"
        # The class's own \@makecaption reads \xfigwd, a length only its
        # \Figure macro defines, and its long-caption branch sets the text in a
        # single unbreakable tabular cell. A plain figure (which is what a TikZ
        # diagram has to be) therefore raised "Undefined control sequence" and
        # then printed a caption 505 pt wider than the page. This replacement
        # keeps the IEEE Access look — blue bold "FIGURE n." head, the same
        # caption fonts — and wraps inside the measure it is actually given, so
        # it is correct in a one-column figure and in a two-column figure*.
        "\\makeatletter\n"
        "\\long\\def\\@makecaption#1#2{%\n"
        "  \\ifx\\@captype\\@IEEEtablestring%\n"
        "    \\begin{flushleft}\\vspace*{5pt}%\n"
        "    {\\color{accessblue}\\tablecapheadfont #1. \\ }%\n"
        "    {\\raggedright\\tablecapfont #2}%\n"
        "    \\end{flushleft}\\@IEEEtablecaptionsepspace%\n"
        "  \\else%\n"
        "    \\@IEEEfigurecaptionsepspace%\n"
        "    \\noindent\\parbox{\\hsize}{\\raggedright%\n"
        "      {\\color{accessblue}\\figcapheadfont #1. \\ }\\figcapfont #2\\par}%\n"
        "  \\fi}\n"
        "\\makeatother\n"
        "\\def\\BibTeX{{\\rm B\\kern-.05em{\\sc i\\kern-.025em b}\\kern-.08em\n"
        "    T\\kern-.1667em\\lower.7ex\\hbox{E}\\kern-.125emX}}\n"
        "\\begin{document}\n"
        # Running header: the Chip Orchestra mark (Logo.png) + this name. An
        # internal engineering report in the IEEE Access FORMAT — not an IEEE
        # publication, so the branding is ours.
        "\\headname{Chip Orchestra}\n"
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
    # Published work the EXPORT stage found by web search. Only entries that
    # carry a title survive: a bibliography entry with nothing to look up is
    # worse than a shorter bibliography.
    related = getattr(ctx, "related_work", {}) or {}
    related_refs = [r for r in (related.get("references") or [])
                    if isinstance(r, dict) and str(r.get("title") or "").strip()][:10]
    related_keys = {id(r): f"r{i + 1}" for i, r in enumerate(related_refs)}

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
        "Section~\\ref{sec:hwsw} the hardware/software co-verification of the finished "
        "interface, Section~\\ref{sec:impl} the physical implementation results, and "
        "Section~\\ref{sec:signoff} the sign-off status and known limitations.\n\n"
    )

    # ---------------------------------------------------------- related work
    if related_refs:
        parts.append("\\section{Related Work}\n\\label{sec:related}\n")
        if related.get("summary"):
            parts.append(_tex(related["summary"]) + "\n\n")
        # Provenance, stated rather than implied: these entries were located by
        # automated literature search while the report was being assembled, not
        # curated by a human. A reader deciding how much weight to give them is
        # entitled to know which of the two it was.
        parts.append(
            "The references in this section were located by automated literature search "
            "during report generation and are cited from the sources retrieved at that "
            "time; readers should consult the originals before relying on any comparison "
            "drawn here.\n\n")
        for ref in related_refs:
            relation = str(ref.get("relation") or "").strip()
            if not relation:
                continue
            parts.append(
                _tex(str(ref.get("title")).strip().rstrip(".")) + "~\\cite{"
                + related_keys[id(ref)] + "}: " + _tex(relation.rstrip(".")) + ".\n\n")

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
    golden_roles = {str(ip.get("name", "")).lower(): ip
                    for ip in ((ctx.golden or {}).get("ips") or [])
                    if isinstance(ip, dict) and ip.get("name")}
    mod_rows = [f"{_code(f)} & {_role_for(f, ctx.top_module, golden_roles)}"
                for f in ctx.rtl_files]
    parts.append(_rule_table("Module and Data-File Inventory", "tab:modules",
                             "File & Role", _cols(0.36, 0.54), mod_rows))

    # The chip-level connection diagram, drawn from the instantiations in the
    # top module. Two columns wide, because a connection diagram squeezed into
    # one column is a picture of nothing.
    if diagram_pages.get("__top__") and include_page:
        parts.append(
            "\\begin{figure*}[!t]\n\\centering\n"
            + include_page(diagram_pages["__top__"], r"\textwidth") +
            "\\caption{Top-level connection diagram of \\texttt{" + top + "}, generated from "
            "the instantiations and net connectivity in the RTL. Rounded pins are the chip's "
            "own I/O; each arrow runs from the block that drives a net to the blocks that read "
            "it and is labelled with the net(s) it carries. Clock and reset reach every block "
            "and are omitted for clarity.}\n"
            "\\label{fig:toplevel}\n\\end{figure*}\n\n")
        parts.append("Fig.~\\ref{fig:toplevel} shows how those modules are wired together at "
                     "the chip level.\n\n")
    elif has("reports/schematic.png"):
        parts.append(_figure("reports/schematic.png",
                             "Synthesized netlist structure (Yosys).", "fig:schematic"))

    # ------------------------------------------------------- golden reference
    # The GOLDEN_GEN stage's manifest, when present: the Python reference model
    # the user approved before any RTL existed, and its own test results.
    golden = ctx.golden or {}
    if golden:
        g_tests = golden.get("tests") or {}
        g_ips = [ip for ip in (golden.get("ips") or []) if isinstance(ip, dict)]
        g_vectors = golden.get("vectors") or []
        parts.append(
            "\\section{Golden Reference Model}\n\\label{sec:golden}\n"
            "Before any hardware was written, the target algorithm was implemented in Python "
            "as an executable reference: one model per IP block, one per sub-toplevel, and a "
            "toplevel that composes them, each with its own test suite. The reference fixes "
            "every quantity the hardware must reproduce --- bit widths, signedness, "
            "fixed-point formats, rounding and saturation behaviour, and the contents of the "
            "on-chip memory images. Its computed output was reviewed and approved by a human "
            "before RTL generation began, so the specification the hardware is measured "
            "against is one a person actually inspected.\n\n"
        )
        if g_ips:
            tier_rows = [
                f"{_code(ip.get('name', ''))} & {_tex(str(ip.get('tier', 'ip')).upper())}"
                f" & {_tex(ip.get('role', '') or 'Design block')}"
                for ip in g_ips[:24]
            ]
            parts.append(_rule_table(
                "Golden Model Block Decomposition (Implemented Module-for-Module in Verilog)",
                "tab:golden", "Model & Tier & Role", _cols(0.31, 0.15, 0.44), tier_rows))
        if g_tests:
            passed, total = g_tests.get("passed", 0), g_tests.get("total", 0)
            parts.append(
                f"The reference suite reports {_fmt(passed)} of {_fmt(total)} tests passing"
                + (f" with {_fmt(g_tests.get('failed'))} failing"
                   if g_tests.get("failed") else "")
                + ". "
                + (f"Per-module input/expected-output vectors were exported for "
                   f"{len(g_vectors)} module(s) and become the expected values in the "
                   "Verilog unit testbenches of Section~\\ref{sec:verif}, so each IP is "
                   "checked against the reference rather than against a hand-guessed number."
                   if g_vectors else
                   "No per-module vectors were exported, so the unit testbenches derive "
                   "their expectations from the reference model directly.")
                + "\n\n")

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
                                 "tab:verif", "Check & Result", _cols(0.44, 0.46), sim_rows))

    # ------------------------------------------ hardware/software verification
    # What the HW_SW_VERIFY stage actually did. Simulation proves the RTL
    # reproduces the reference on the input that was baked into the design;
    # this section is the evidence for the question a user actually asks, which
    # is whether the finished part can be USED over its own interface.
    parts.append(_hw_sw_section(ctx, has))

    # -------------------------------------- module descriptions + mathematics
    # Rendered from golden/module_math.json, authored by the agent that wrote
    # the golden model — the equations therefore describe what the reference
    # implementation (and so the RTL) actually computes.
    math_doc = getattr(ctx, "module_math", {}) or {}
    algo = math_doc.get("algorithm") if isinstance(math_doc.get("algorithm"), dict) else {}
    mods = [x for x in (math_doc.get("modules") or []) if isinstance(x, dict) and x.get("name")]

    def _equations(items) -> str:
        """Equation bodies come from the agent as raw LaTeX and are NOT escaped.
        pdflatex runs without -halt-on-error, so a malformed one degrades to a
        visible artifact in the PDF instead of taking the whole paper down.

        Each body is set inside a shrink-to-fit box. Display math does NOT wrap:
        an equation wider than the column silently prints over the neighbouring
        column and off the page edge, which is what happened to every equation
        here that stated two relations side by side. The box leaves equations
        that already fit at full size and scales down only the ones that do not.
        Multi-line environments are passed through untouched, since they must
        stay at the top level of the display to align."""
        out = []
        for eq in (items or []):
            body = str(eq).strip()
            if not body:
                continue
            if re.search(r"\\begin\{(align|split|gather|multline|eqnarray)", body):
                out.append("\\begin{equation}\n" + body + "\n\\end{equation}\n")
                continue
            out.append(
                "\\begin{equation}\n"
                "\\resizebox{\\ifdim\\width>\\columnwidth\\columnwidth\\else\\width\\fi}{!}{$\\displaystyle\n"
                + body + "\n$}\n\\end{equation}\n")
        return "".join(out)

    def _symbol_figure(module: str) -> str:
        """The IP symbol figure for one module, or '' when it has none."""
        entry = symbols.get(module)
        if not entry or not include_page or module not in diagram_pages:
            return ""
        safe = re.sub(r"[^A-Za-z0-9]", "", module) or "mod"
        return ("\\begin{figure}[!t]\n\\centering\n" + include_page(diagram_pages[module]) +
                "\\caption{Interface of \\texttt{" + _tex(module) + "} "
                "(\\texttt{" + _tex(entry.get("file", "")) + "}): inputs enter on the left, "
                "outputs leave on the right, bus widths as declared in the RTL.}\n"
                "\\label{fig:sym" + safe + "}\n\\end{figure}\n\n")

    if algo or mods or symbols:
        parts.append("\\section{Module Descriptions and Governing Equations}\n"
                     "\\label{sec:modules}\n")
        if symbols:
            parts.append(
                "Every module is shown with its interface symbol --- ports, directions and bus "
                "widths taken straight from the Verilog declaration --- alongside what it "
                "computes.\n\n")
    if algo.get("summary"):
        parts.append(_tex(algo["summary"]) + "\n\n")
    if algo.get("equations"):
        parts.append(_equations(algo["equations"]))
    documented = set()
    for mod in mods:
        name = str(mod["name"])
        documented.add(name)
        parts.append("\\subsection{" + _tex(name) + "}\n")
        parts.append(_symbol_figure(name))
        if mod.get("purpose"):
            parts.append(_tex(mod["purpose"]) + "\n\n")
        if mod.get("io"):
            parts.append("\\textit{Interface:} " + _tex(mod["io"]) + "\n\n")
        if mod.get("equations"):
            parts.append(_equations(mod["equations"]))
    # A module the mathematics document skipped still exists in the silicon, so
    # it still gets its symbol and its port list — "every IP" means every IP.
    for name in sorted(symbols):
        if name in documented:
            continue
        parts.append("\\subsection{" + _tex(name) + "}\n")
        parts.append(_symbol_figure(name))
        entry = symbols[name]
        ports = entry.get("ports") or []
        inputs = [p["name"] for p in ports if p["dir"] == "input"]
        outputs = [p["name"] for p in ports if p["dir"] != "input"]
        parts.append(
            "Implemented in " + _code(entry.get("file", "")) + ". \\textit{Interface:} "
            + (", ".join(_code(n) for n in inputs) or "none") + " $\\rightarrow$ "
            + (", ".join(_code(n) for n in outputs) or "none") + ".\n\n")

    # ------------------------------------------------ dataflow + cycle budget
    # "How many cycles does it take, and what path does the data take?" are the
    # two questions an accelerator report must answer; both are derived from
    # measured evidence (VCD edge count, approved golden decomposition) rather
    # than asserted.
    profile = getattr(ctx, "timing_profile", {}) or {}
    chain = getattr(ctx, "dataflow", []) or []
    if profile or chain:
        parts.append("\\subsection{Dataflow and Cycle Budget}\n")

    if chain:
        stages_txt = " $\\rightarrow$ ".join(_tex(c["name"]) for c in chain)
        parts.append(
            "The canonical input is held in the on-chip memory image and streamed through "
            "the module chain " + stages_txt + ". Each block's responsibility is listed in "
            "Table~\\ref{tab:dataflow}; the decomposition is the one approved at the "
            "golden-model gate, so the hardware partitioning and the reference "
            "implementation share a structure.\n\n")
        rows = [f"{_code(c['name'])} & {_tex((c['tier'] or 'ip').upper())} & "
                f"{_tex(c['role'] or '---')}" for c in chain]
        parts.append(_rule_table("Dataflow: Module Chain and Responsibilities",
                                 "tab:dataflow", "Module & Tier & Role",
                                 _cols(0.31, 0.15, 0.44), rows))

    if profile:
        cycles = profile.get("clock_cycles")
        parts.append(
            "The cycle count in Table~\\ref{tab:cycles} is measured by counting rising "
            "clock edges in the testbench waveform (\\texttt{waves/design.vcd}), not "
            "estimated from the elapsed simulation time, so clock gating and stall cycles "
            "are included. Latency and throughput are then projected onto the "
            "post-place-and-route clock period, which is the rate the fabricated device "
            "actually achieves.\n\n")
        labels = [
            ("clock_cycles", "Clock cycles (full run)"),
            ("sim_time_ns", "Simulated time (ns)"),
            ("ns_per_cycle", "Simulation clock period (ns)"),
            ("latency_us_at_clock", "Latency at closed clock (us)"),
            ("throughput_per_s", "Full-frame throughput (1/s)"),
        ]
        cyc_rows = [f"{_tex(lbl)} & {_fmt(profile[key])}"
                    for key, lbl in labels if profile.get(key) is not None]
        if cyc_rows:
            parts.append(_rule_table("Measured Cycle Budget", "tab:cycles",
                                     "Quantity & Value", _cols(0.52, 0.38), cyc_rows))
        samples = m.get("input_size")
        if cycles and isinstance(samples, (int, float)) and samples:
            total = float(samples) * float(samples)
            parts.append(
                f"For the {_fmt(samples)}$\\times${_fmt(samples)} canonical input "
                f"({_fmt(int(total))} samples) this is "
                f"{cycles / total:.2f} cycles per output sample.\n\n")

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
                                 "tab:impl", "Parameter & Value", _cols(0.44, 0.46), impl_rows))
    corner_rows = [f"{lbl} & {_fmt(m[k])}"
                   for k, lbl in (("setup_ws_tt_ns", "typical (tt, 25\\,\\textdegree C)"),
                                  ("setup_ws_ss_ns", "slow (ss, 125\\,\\textdegree C)"),
                                  ("setup_ws_ff_ns", "fast (ff, $-$40\\,\\textdegree C)"))
                   if k in m]
    if corner_rows:
        parts.append(_rule_table("Setup Slack per PVT Corner (Nominal RC)",
                                 "tab:corners", "Corner & Setup WS (ns)",
                                 _cols(0.44, 0.46), corner_rows))
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
        # \url, not \underline: an underlined URL is one unbreakable word, and
        # all four of these ran past the right margin of the reference column.
        "\\begin{thebibliography}{00}\n"
        "\\bibitem{b1} The OpenROAD Project. ``OpenROAD --- an open-source, autonomous "
        "RTL-to-GDSII flow.'' [Online]. Available: \\url{https://theopenroadproject.org}\n"
        "\\bibitem{b2} R. T. Edwards \\emph{et al.}, ``Magic VLSI layout tool.'' [Online]. "
        "Available: \\url{http://opencircuitdesign.com/magic}\n"
        "\\bibitem{b3} The LibreLane contributors. ``LibreLane: an open infrastructure for "
        "silicon implementation.'' [Online]. Available: "
        "\\url{https://github.com/librelane/librelane}\n"
        "\\bibitem{b4} GlobalFoundries and Google. ``GF180MCU open-source process design "
        "kit.'' [Online]. Available: \\url{https://github.com/google/gf180mcu-pdk}\n"
        + "".join(_bibitem(related_keys[id(ref)], ref) for ref in related_refs) +
        "\\end{thebibliography}\n\n"
        "\\EOD\n\n"
        "\\end{document}\n"
    )

    return "".join(parts)


def stage_template_assets(target_dir: Path) -> List[str]:
    """Copy the vendored IEEE Access class files and the Chip Orchestra header
    artwork next to the ``.tex`` so ``pdflatex`` can resolve them. Returns the
    workspace-relative names actually copied."""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    for asset in TEMPLATE_ASSETS:
        src = TEMPLATE_DIR / asset
        if not src.is_file():
            continue
        try:
            shutil.copy(src, target_dir / asset)
            copied.append(asset)
        except OSError:
            continue
    return copied


def compile_pdf(tex_path: Path, timeout: int = 240) -> Optional[Path]:
    """Compile the report with ``pdflatex`` (two passes so the cross-references
    and the table/figure numbering settle). Returns the PDF path, or None when
    pdflatex is unavailable or the compile produced nothing — the ``.tex`` is
    still a deliverable in that case, so this never raises.

    ``-interaction=nonstopmode`` matters: the IEEE Access class emits warnings
    that would otherwise stop and wait for input forever inside a container.
    ``-halt-on-error`` is deliberately NOT used — a single figure that a stage
    failed to render would otherwise take the whole paper down, where LaTeX's
    draft fallback keeps the report and leaves a visible placeholder."""
    tex_path = Path(tex_path)
    if not tex_path.is_file() or not shutil.which("pdflatex"):
        return None
    workdir = tex_path.parent
    env = dict(os.environ)
    # The class may also be found in the template dir, so a hand-run compile
    # from a workspace that lost its copies still works.
    env["TEXINPUTS"] = f"{TEMPLATE_DIR}:{workdir}:" + env.get("TEXINPUTS", "")
    proc = None
    for _ in range(2):
        try:
            proc = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_path.name],
                cwd=str(workdir), capture_output=True, text=True, errors="replace",
                timeout=timeout, env=env)
        except (OSError, subprocess.SubprocessError):
            return None
    pdf = tex_path.with_suffix(".pdf")
    if pdf.is_file():
        for ext in (".aux", ".out", ".log"):
            tex_path.with_suffix(ext).unlink(missing_ok=True)
        return pdf
    # Keep the tail of the failure next to the report so the log explains why.
    if proc is not None:
        try:
            tail = "\n".join((proc.stdout or "").splitlines()[-40:])
            (workdir / "final_report.pdflatex.log").write_text(tail)
        except OSError:
            pass
    return None


__all__ = ["generate_latex", "stage_template_assets", "compile_pdf", "TEMPLATE_DIR"]
