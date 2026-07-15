"""User-attached file (image / PDF / text) ingestion — ported from GarudaChip.

Attachments arrive in the task workspace at ``context/uploads/`` (the
orchestrator writes them there at task creation; the invoke API also accepts
base64 attachments directly). :func:`ingest_uploads` builds a DIGEST the deep
agents peek at:

* images  → described by a VISION model (``llm.describe_image``): blocks,
  labels, bit-widths, connections — a structural spec, not OCR label soup.
  A transient vision failure is retried; if no vision model exists the agent
  is told to open the image itself with run_python + PIL.
* PDFs    → text-extracted best-effort (with OCR fallback, see extract.py);
* text    → embedded (capped).

The digest is persisted to ``context/uploads_digest.md`` so every later stage
(and every deep agent, via read_file_disk) sees the same reading of the
attachment without re-running vision.
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import List, Optional

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

DIGEST_REL = "context/uploads_digest.md"
MANIFEST_REL = "context/uploads_manifest.json"

# Roles an uploaded image can play — they demand DIFFERENT workflow behaviour:
#   architecture — a block diagram/schematic: the RTL is BUILT TO it;
#   data         — content the chip should PROCESS: preprocess into a .mem
#                  stimulus, never turn its shapes into modules;
#   reference    — background info only.
_ROLE_ARCHITECTURE = "architecture"
_ROLE_DATA = "data"
_ROLE_REFERENCE = "reference"

_DATA_BRIEF_RE = re.compile(
    r"\b(image|pixel|photo|camera|frame|maze|grid|map|pattern|detect|classif|inferen|"
    r"segment|convolut|cnn|filter|denois|edge)\b", re.I)
_ARCH_BRIEF_RE = re.compile(
    r"\b(diagram|architecture|block|schematic|like (this|the) (image|picture|diagram)|"
    r"seperti gambar)\b", re.I)


def _classify_image(path: Path, brief: str) -> str:
    """What ROLE does this image play for the design? Asks the vision model
    (with the design brief as context); falls back to a brief-keyword heuristic
    when vision is unavailable."""
    try:
        from llm import describe_image, model_supports_vision
        if model_supports_vision():
            answer = describe_image(path, prompt=(
                "You are triaging an image attached to a chip-design request.\n"
                f"DESIGN REQUEST: {brief[:500]}\n"
                "Classify the image's ROLE for this chip project. Answer with EXACTLY one word:\n"
                "- architecture — a hardware block diagram, schematic, or datasheet figure the "
                "RTL should be built to;\n"
                "- data — content the finished chip is supposed to PROCESS as input (a photo, "
                "scene, game grid/maze, pattern, signal plot, test picture);\n"
                "- reference — anything else (background information only)."), temperature=0.0)
            low = (answer or "").strip().lower()
            for role in (_ROLE_ARCHITECTURE, _ROLE_DATA, _ROLE_REFERENCE):
                if role in low:
                    return role
    except Exception:  # noqa: BLE001
        pass
    if _ARCH_BRIEF_RE.search(brief or ""):
        return _ROLE_ARCHITECTURE
    if _DATA_BRIEF_RE.search(brief or ""):
        return _ROLE_DATA
    return _ROLE_REFERENCE


_ROLE_GUIDANCE = {
    _ROLE_ARCHITECTURE: (
        "ROLE: ARCHITECTURE — this is the build spec. Construct the RTL module map to "
        "match this diagram's blocks, connections, and widths. Do NOT feed this image "
        "into the chip as data."),
    _ROLE_DATA: (
        "ROLE: CHIP INPUT DATA — the finished chip must PROCESS this content. Do NOT "
        "derive modules from its shapes. At testbench time, preprocess THIS file with "
        "run_python (PIL/numpy) into the chip's input format (rtl/<name>.mem via "
        "$readmemh) and visualize it to waves/chip_input.png."),
    _ROLE_REFERENCE: (
        "ROLE: REFERENCE — background information only; use it to understand the "
        "request, not as a build contract or chip input."),
}


def _extract_pdf_text(path: Path) -> str:
    """Best-effort PDF → text (first 20 pages) WITH OCR fallback for scanned
    pages, cleaned of references/header-footer chrome (see extract.py)."""
    try:
        from extract import pdf_to_text
        return pdf_to_text(path)
    except Exception:  # noqa: BLE001
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages[:20]).strip()
        except Exception:  # noqa: BLE001
            return ""


def save_attachments(workspace: Path, attachments: List[dict]) -> List[Path]:
    """Persist base64 attachments ({'name', 'content_base64'}) under
    context/uploads/. Returns the saved paths."""
    updir = workspace / "context" / "uploads"
    updir.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    for att in attachments or []:
        name = re.sub(r"[^\w.\-]", "_", os.path.basename(str(att.get("name") or "upload")))
        raw = att.get("content_base64") or att.get("content") or ""
        try:
            data = base64.b64decode(raw)
        except Exception:  # noqa: BLE001
            continue
        p = updir / name
        p.write_bytes(data)
        saved.append(p)
        if p.suffix.lower() in _IMAGE_EXT:
            # RECORD this as a REAL user upload so later steps use THIS image,
            # never an agent-generated file that lands in context/uploads.
            with open(updir / ".user_images.txt", "a") as mf:
                mf.write(name + "\n")
    return saved


def ingest_uploads(workspace: Path, force: bool = False, brief: str = "") -> str:
    """Build (or return the cached) uploads digest for a task workspace. Scans
    ``context/uploads/``, CLASSIFIES each image's role (architecture spec vs.
    chip-input data vs. reference — they demand different workflow behaviour),
    and describes every attachment the way GarudaChip's ``_save_uploads`` does.
    Roles are persisted to ``context/uploads_manifest.json``. Returns the
    digest markdown ('' when no uploads)."""
    workspace = Path(workspace)
    updir = workspace / "context" / "uploads"
    digest_path = workspace / DIGEST_REL
    if not updir.is_dir():
        return ""
    files = [p for p in sorted(updir.iterdir())
             if p.is_file() and not p.name.startswith(".")]
    if not files:
        return ""
    if digest_path.is_file() and not force:
        return digest_path.read_text(errors="replace")

    manifest: dict = {}
    parts: List[str] = []
    for path in files:
        name = path.name
        rel = path.relative_to(workspace)
        ext = path.suffix.lower()
        size = path.stat().st_size
        if ext in _IMAGE_EXT:
            role = _classify_image(path, brief)
            manifest[name] = role
            # VISION ONLY, with a ROLE-APPROPRIATE prompt: a block diagram is
            # read structurally (blocks/connections/widths); chip-input data is
            # read as content (what the chip must compute from it). A transient
            # vision failure is RETRIED, never OCR-degraded.
            prompt = "" if role == _ROLE_ARCHITECTURE else (
                "Describe this image as INPUT DATA for a hardware accelerator: what it "
                "depicts, its grid/pixel structure and dimensions, which colors/values "
                "carry meaning, and what a chip processing it would compute. Be precise "
                "and structural — sizes, coordinates, value ranges." if role == _ROLE_DATA
                else "Describe this image concisely for an RTL engineer: what it shows and "
                     "which details could matter for the chip design request.")
            vision = ""
            try:
                from llm import describe_image, model_supports_vision
                if model_supports_vision():
                    for _try in range(3):
                        vision = (describe_image(path, prompt=prompt) or "").strip()
                        if vision:
                            break
            except Exception:  # noqa: BLE001
                vision = ""
            guidance = _ROLE_GUIDANCE[role]
            if vision:
                parts.append(f"### {name} (image · {role.upper()})\n"
                             f"Saved at `{rel}`. {guidance}\n{vision[:6000]}\n"
                             "Open the image with run_python (PIL) only if you need a finer detail.")
            else:
                parts.append(f"### {name} (image · {role.upper()} · {size} bytes)\n"
                             f"Saved at `{rel}`. {guidance}\n"
                             "The vision model could not read it — open it with run_python "
                             "(PIL.Image) to inspect its contents; do NOT guess what it shows.")
        elif ext == ".pdf":
            text = _extract_pdf_text(path)
            parts.append(f"### {name} (PDF)\n{text[:6000]}" if text else
                         f"### {name} (PDF · {size} bytes)\nSaved at `{rel}`. "
                         "Extract its text with run_python (pip_install pypdf) if needed.")
        else:
            try:
                parts.append(f"### {name}\n```\n{path.read_bytes().decode('utf-8', 'replace')[:6000]}\n```")
            except Exception:  # noqa: BLE001
                parts.append(f"### {name} ({size} bytes)\nSaved at `{rel}` (binary).")

    digest = ("# User-attached files (uploaded with the task)\n\n" + "\n\n".join(parts)) if parts else ""
    if digest:
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        digest_path.write_text(digest)
    if manifest:
        try:
            import json
            (workspace / MANIFEST_REL).write_text(json.dumps(manifest, indent=1))
        except Exception:  # noqa: BLE001
            pass
    return digest


def uploads_manifest(workspace: Optional[Path]) -> dict:
    """{image name: role} from the ingest classification ('' role map when absent)."""
    if workspace is None:
        return {}
    p = Path(workspace) / MANIFEST_REL
    if not p.is_file():
        return {}
    try:
        import json
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return {}


def load_uploads_digest(workspace: Optional[Path]) -> str:
    """The cached uploads digest for a workspace ('' when absent)."""
    if workspace is None:
        return ""
    p = Path(workspace) / DIGEST_REL
    return p.read_text(errors="replace") if p.is_file() else ""


def user_image(workspace: Path) -> "Path | None":
    """The most recent REAL user-uploaded image (never an agent-generated file
    that landed in context/uploads)."""
    updir = Path(workspace) / "context" / "uploads"
    marker = updir / ".user_images.txt"
    if marker.is_file():
        names = [n for n in marker.read_text().splitlines() if n.strip()]
        for n in reversed(names):
            p = updir / n
            if p.is_file():
                return p
    if updir.is_dir():
        imgs = [p for p in sorted(updir.iterdir(), key=lambda q: q.stat().st_mtime)
                if p.suffix.lower() in _IMAGE_EXT]
        if imgs:
            return imgs[-1]
    return None


__all__ = ["save_attachments", "ingest_uploads", "load_uploads_digest", "user_image",
           "uploads_manifest", "DIGEST_REL", "MANIFEST_REL"]
