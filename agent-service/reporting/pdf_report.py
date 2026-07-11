"""PDF report assembly.

Collects the markdown reports and rendered PNG visuals produced across the flow
(schematic, waveform, GDS, metrics chart) and assembles them into a single
``exports/final_report.pdf``. Uses reportlab; if reportlab is unavailable the
function degrades gracefully and returns ``None`` so the flow still completes.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .evidence import ReportContext

PDF_PATH = "exports/final_report.pdf"

# Visuals we look for, in presentation order, with human captions.
_VISUALS = [
    ("reports/schematic.png", "Synthesized Schematic (Yosys)"),
    ("waves/waveform.png", "Simulation Waveform"),
    ("reports/waveform.png", "Simulation Waveform"),
    ("gds/layout.png", "GDSII Layout (KLayout)"),
    ("reports/gds.png", "GDSII Layout"),
    ("reports/metrics.png", "Physical Metrics"),
]


def _strip_md(text: str) -> List[str]:
    """Very small markdown -> plain-paragraph flattening for PDF body text."""
    out: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            continue
        line = re.sub(r"`([^`]*)`", r"\1", line)
        line = re.sub(r"\*\*([^*]*)\*\*", r"\1", line)
        out.append(line)
    return out


def generate_pdf(workspace: Path, ctx: ReportContext) -> Optional[str]:
    workspace = Path(workspace)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import (
            Image,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.lib import colors
    except ImportError:
        return None

    out_path = workspace / PDF_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9, leading=12)
    mono = ParagraphStyle("mono", parent=styles["BodyText"], fontName="Courier", fontSize=7.5, leading=9)
    story = []

    story.append(Paragraph(f"Chip Orchestra — Final Report", styles["Title"]))
    story.append(Paragraph(f"{ctx.task_name}", styles["Heading2"]))
    story.append(Spacer(1, 0.3 * cm))

    signoff_state = "TAPEOUT READY" if ctx.tapeout_ready else "NOT tapeout ready"
    summary_rows = [
        ["Task ID", ctx.task_id or "n/a"],
        ["Top module", ctx.top_module or "n/a"],
        ["Signoff", signoff_state],
        ["RTL files", str(len(ctx.rtl_files))],
        ["Waveforms", str(len(ctx.wave_files))],
        ["GDS files", str(len(ctx.gds_files))],
    ]
    for key, value in list(ctx.metrics.items())[:10]:
        summary_rows.append([str(key), str(value)])
    table = Table(summary_rows, colWidths=[5 * cm, 11 * cm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 0.4 * cm))

    # Visuals
    seen = set()
    for rel, caption in _VISUALS:
        img = workspace / rel
        if not img.is_file() or rel in seen:
            continue
        seen.add(rel)
        try:
            reader = ImageReader(str(img))
            iw, ih = reader.getSize()
            max_w = 16 * cm
            scale = min(1.0, max_w / iw)
            story.append(Paragraph(caption, styles["Heading3"]))
            story.append(Image(str(img), width=iw * scale, height=ih * scale))
            story.append(Spacer(1, 0.3 * cm))
        except Exception:
            continue

    # Markdown report bodies
    report_docs = [
        ("Final Design Report", workspace / "reports/final_design_report.md"),
        ("Architecture Overview", workspace / "reports/architecture_overview.md"),
        ("Signoff Summary", workspace / "reports/signoff_summary.md"),
        ("Runbook", workspace / "reports/runbook.md"),
    ]
    for title, path in report_docs:
        if not path.is_file():
            continue
        story.append(PageBreak())
        story.append(Paragraph(title, styles["Heading2"]))
        story.append(Spacer(1, 0.2 * cm))
        for line in _strip_md(path.read_text(errors="replace")):
            if not line.strip():
                story.append(Spacer(1, 0.15 * cm))
            elif line.startswith("#"):
                story.append(Paragraph(line.lstrip("# ").strip(), styles["Heading3"]))
            elif line.lstrip().startswith(("|", "iverilog", "vvp", "librelane")):
                story.append(Paragraph(line.replace(" ", "&nbsp;"), mono))
            else:
                story.append(Paragraph(line, body))

    try:
        doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                                leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=1.5 * cm, bottomMargin=1.5 * cm)
        doc.build(story)
    except Exception:
        return None
    return PDF_PATH


__all__ = ["generate_pdf", "PDF_PATH"]
