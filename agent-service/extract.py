"""Document extractor + OCR for GarudaChip's knowledge pipeline.

ONE place that turns a file (PDF / image / text) into clean, search-worthy text, so the
knowledge store (memory_store.ingest_file) and the research/upload paths (app.py) all get
the REAL content — not a "PDF document: paper.pdf" placeholder.

Design goals (the user's ask: "make the extractor & OCR work and keep only correlated info"):
  • PDF → text with pypdf; any page that comes back near-EMPTY (a scanned page or a
    figure-only page) is OCR'd by rendering it with `pdftoppm` and reading it with
    `tesseract` — so figure/scan-heavy datasheets still yield text.
  • IMAGE → text with `tesseract` (a schematic/screenshot/datasheet photo becomes text).
  • CLEAN the result: collapse whitespace, drop page-number / header-footer chrome and the
    trailing References/Acknowledgements boilerplate, de-duplicate repeated lines — keep the
    technical substance, throw away the noise.
  • RELEVANCE: `relevant_to(text, query)` lets a caller drop a chunk that isn't correlated
    with the design being built.

Everything is best-effort and dependency-light: it shells out to the already-installed
`pdftoppm` (poppler) and `tesseract` binaries, so no extra Python package is required. If a
tool is missing it degrades gracefully (returns whatever text it could get).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}

# A page yielding fewer than this many extractable characters is treated as scanned/figure-only
# and sent to OCR. Tunable so a noisy corpus can raise/lower the trigger.
_OCR_PAGE_MIN_CHARS = int(os.getenv("GARUDA_OCR_PAGE_MIN_CHARS", "120"))
_OCR_DPI = int(os.getenv("GARUDA_OCR_DPI", "200"))
_MAX_PAGES = int(os.getenv("GARUDA_EXTRACT_MAX_PAGES", "20"))
_TESS_TIMEOUT = int(os.getenv("GARUDA_TESSERACT_TIMEOUT_S", "40"))


def have_ocr() -> bool:
    """True when both the renderer (poppler `pdftoppm`) and `tesseract` are on PATH."""
    return bool(shutil.which("tesseract"))


def _tesseract_on(image_path: str) -> str:
    """OCR one image file → text via the tesseract CLI (no pytesseract dependency)."""
    if not shutil.which("tesseract"):
        return ""
    try:
        proc = subprocess.run(["tesseract", str(image_path), "stdout"],
                              capture_output=True, text=True, timeout=_TESS_TIMEOUT)
        return proc.stdout if proc.returncode == 0 else ""
    except Exception:  # noqa: BLE001 — OCR is best-effort
        return ""


def _ocr_pdf_page(pdf_path: Path, page_1based: int) -> str:
    """Render ONE PDF page to PNG with pdftoppm, OCR it, return the text. Empty on any failure."""
    if not (shutil.which("pdftoppm") and shutil.which("tesseract")):
        return ""
    tmp = tempfile.mkdtemp(prefix="garuda_ocr_")
    try:
        prefix = os.path.join(tmp, "pg")
        subprocess.run(["pdftoppm", "-png", "-r", str(_OCR_DPI),
                        "-f", str(page_1based), "-l", str(page_1based), str(pdf_path), prefix],
                       capture_output=True, text=True, timeout=_TESS_TIMEOUT)
        pngs = sorted(Path(tmp).glob("*.png"))
        return _tesseract_on(str(pngs[0])) if pngs else ""
    except Exception:  # noqa: BLE001
        return ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pdf_to_text(path, max_pages: int = _MAX_PAGES, ocr: bool = True) -> str:
    """PDF → text. pypdf first; any page that extracts almost nothing is OCR'd (scanned/figure
    page). Returns cleaned text (capped to `max_pages`)."""
    path = Path(path)
    pages_text: list[str] = []
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        n = min(len(reader.pages), max_pages)
        for i in range(n):
            try:
                t = (reader.pages[i].extract_text() or "").strip()
            except Exception:  # noqa: BLE001
                t = ""
            if ocr and len(t) < _OCR_PAGE_MIN_CHARS and have_ocr():
                ocr_t = _ocr_pdf_page(path, i + 1).strip()
                if len(ocr_t) > len(t):
                    t = ocr_t
            if t:
                pages_text.append(t)
    except Exception:  # noqa: BLE001 — pypdf missing/corrupt → fall back to whole-doc OCR
        pages_text = []
    text = "\n\n".join(pages_text).strip()
    # A born-digital PDF that pypdf couldn't read at all → OCR the first few pages wholesale.
    if not text and ocr and have_ocr():
        text = "\n\n".join(filter(None, (_ocr_pdf_page(path, i + 1)
                                          for i in range(min(max_pages, 6))))).strip()
    return clean_text(text)


def image_to_text(path) -> str:
    """Image → text via OCR (cleaned). '' if tesseract is unavailable or the image has no text."""
    return clean_text(_tesseract_on(str(path)))


def file_to_text(path) -> str:
    """Best-effort text for ANY supported file: PDF (with OCR fallback), image (OCR), or a
    plain-text/code/markdown file. '' for an unsupported/empty/binary file. This is the single
    entry point the knowledge store uses so a PDF/image is INDEXED by its real content."""
    p = Path(path)
    if not p.is_file():
        return ""
    ext = p.suffix.lower()
    if ext == ".pdf":
        return pdf_to_text(p)
    if ext in IMAGE_EXT:
        return image_to_text(p)
    try:
        return clean_text(p.read_text(errors="replace"))
    except Exception:  # noqa: BLE001
        return ""


# --- cleaning: keep the substance, drop the noise ---------------------------
_REF_HEADING = re.compile(
    r"^\s*(references|bibliography|acknowledgements?|acknowledgments?)\s*$", re.I)
_PAGE_NUM = re.compile(r"^\s*(page\s*)?\d{1,4}\s*(/\s*\d{1,4})?\s*$", re.I)
_URL_ONLY = re.compile(r"^\s*(https?://\S+|www\.\S+)\s*$", re.I)


def clean_text(text: str) -> str:
    """Trim a raw extraction down to its useful core:
      • normalize whitespace, drop blank-heavy runs;
      • remove page-number-only and bare-URL lines (PDF header/footer chrome);
      • CUT the trailing References/Bibliography/Acknowledgements section — for an RTL agent
        that tail is citation noise, not design knowledge;
      • collapse a line repeated many times (a running header/footer) to one.
    Conservative: if cutting would leave almost nothing, the cut is skipped."""
    if not text:
        return ""
    lines = [ln.rstrip() for ln in text.replace("\r", "\n").split("\n")]
    # cut everything from a standalone References/Bibliography heading onward (keep >40% of doc)
    for i, ln in enumerate(lines):
        if _REF_HEADING.match(ln) and i > len(lines) * 0.4:
            lines = lines[:i]
            break
    seen: dict[str, int] = {}
    out: list[str] = []
    blanks = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            blanks += 1
            if blanks <= 1:
                out.append("")
            continue
        blanks = 0
        if _PAGE_NUM.match(s) or _URL_ONLY.match(s):
            continue
        # a header/footer line repeats on every page — keep the first 2, drop the rest
        seen[s] = seen.get(s, 0) + 1
        if seen[s] > 2 and len(s) < 80:
            continue
        out.append(ln)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return cleaned


_WORD = re.compile(r"[A-Za-z0-9_]+")


def relevant_to(text: str, query: str, min_overlap: int = 2) -> bool:
    """True if `text` is correlated with `query` — at least `min_overlap` of the query's
    distinctive (4+ char) terms appear in it. Lets a caller DROP an extracted page that has
    nothing to do with the design being built (the 'get rid of uncorrelated info' ask). A short
    query (few distinctive terms) always passes, so we never over-filter."""
    q_terms = {w.lower() for w in _WORD.findall(query or "") if len(w) >= 4}
    if len(q_terms) < min_overlap:
        return True
    body = set(w.lower() for w in _WORD.findall(text or ""))
    return len(q_terms & body) >= min_overlap
