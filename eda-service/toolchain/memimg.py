"""Deterministic, format-aware hex ``.mem`` → PNG rendering for chip outputs.

Ported from GarudaChip's ``_render_mem_image``. Testbenches dump three shapes:
  a) N² packed 24-bit words → unpack to RGB;
  b) 3·N² interleaved R,G,B BYTES (a byte-array $writememh) → group triplets;
  c) N² small grayscale values → autoscaled gray.

``$writememh`` annotates dumps with ``// 0x10`` address comments and
``$readmemh`` files may carry ``@40`` directives — both are stripped BEFORE
tokenizing (parsing the address token salts fake "pixels" into the image).
"""
from __future__ import annotations

import math
import re
from pathlib import Path


def _read_values(mem_path: Path) -> list:
    body = re.sub(r"//[^\n]*", " ", mem_path.read_text(errors="replace"))
    vals = []
    for tok in body.split():
        if tok.startswith("@"):
            continue
        try:
            vals.append(int(tok, 16))
        except ValueError:
            pass
    return vals


def infer_size(workspace: Path, count: int, max_val: int) -> int:
    """The image side length: the run's authoritative context/input_size.txt when
    present (GarudaChip convention), else inferred from the value count."""
    marker = workspace / "context" / "input_size.txt"
    if marker.is_file():
        try:
            n = int(marker.read_text().strip())
            if n > 0:
                return n
        except ValueError:
            pass
    if count >= 3 and max_val <= 255:
        rgb_side = int(math.isqrt(count // 3))
        if rgb_side * rgb_side * 3 == count:
            return rgb_side
    side = int(math.isqrt(count))
    return side if side > 0 else 0


def render_mem_image(mem_path: Path, out_png: Path, size: int = 0,
                     workspace: "Path | None" = None) -> bool:
    """Render a hex .mem dump to a PNG (upscaled, nearest). Returns True on
    success; never raises (best-effort display, must not fail the stage)."""
    try:
        vals = _read_values(Path(mem_path))
        if not vals:
            return False
        import numpy as np
        from PIL import Image

        n, mx = len(vals), max(vals)
        if not size:
            size = infer_size(workspace or Path(mem_path).parent.parent, n, mx)
        if size < 2:
            return False
        if n >= 3 * size * size and mx <= 255:
            arr = np.array(vals[:3 * size * size], dtype="uint8").reshape(size, size, 3)
        elif n >= size * size and mx > 255:
            a = np.array(vals[:size * size], dtype="uint32").reshape(size, size)
            arr = np.stack([(a >> 16) & 255, (a >> 8) & 255, a & 255],
                           axis=-1).astype("uint8")
        else:
            k = size * size
            a = np.array((vals + [0] * k)[:k], dtype="uint16").reshape(size, size)
            arr = (a.astype("float32") * 255.0 / (int(a.max()) or 1)).astype("uint8")
        Image.fromarray(arr).resize((256, 256), Image.NEAREST).save(out_png)
        return True
    except Exception:  # noqa: BLE001
        return False


__all__ = ["render_mem_image", "infer_size"]
