"""Hex ``.mem`` → PNG rendering for the agent service.

``eda-service/toolchain/memimg.py`` renders the chip's dumped result during SIM.
GOLDEN_GEN needs the same picture much earlier — its human approval gate has to
SHOW the user what the golden model computed, and SIM has not run yet — so the
rendering lives here too, matching that module's palette and size inference so
the golden, input and chip renders stay directly comparable.

Deliberately Pillow-only (no numpy): pillow is a service dependency, whereas
numpy is installed on demand into the agents' sandbox and is not importable from
the service process itself.

``$writememh`` annotates dumps with ``// 0x10`` address comments and
``$readmemh`` files may carry ``@40`` directives — both are stripped BEFORE
tokenizing (parsing an address token salts fake "pixels" into the image).
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import List, Optional

# Categorical legend, identical to eda-service's: index == cell value.
_PALETTE = [
    (255, 255, 255),  # 0 free — white
    (0, 0, 0),        # 1 wall — black
    (220, 40, 40),    # 2 start — red
    (40, 190, 80),    # 3 goal — green
    (60, 110, 245),   # 4 path — blue
    (250, 160, 30),   # 5 — orange
    (160, 70, 220),   # 6 — purple
    (40, 200, 220),   # 7 — cyan
    (240, 220, 60),   # 8 — yellow
    (230, 80, 200),   # 9 — magenta
]


def read_values(mem_path: Path) -> List[int]:
    """Hex tokens of a .mem file, ignoring comments and @address directives."""
    try:
        body = re.sub(r"//[^\n]*", " ", Path(mem_path).read_text(errors="replace"))
    except OSError:
        return []
    vals: List[int] = []
    for tok in body.split():
        if tok.startswith("@"):
            continue
        try:
            vals.append(int(tok, 16))
        except ValueError:
            pass
    return vals


def infer_size(workspace: Path, count: int, max_val: int) -> int:
    """Image side length: the run's authoritative ``context/input_size.txt``
    when present, else inferred from how many values were dumped."""
    marker = Path(workspace) / "context" / "input_size.txt"
    if marker.is_file():
        try:
            n = int(marker.read_text().strip())
            # The marker describes the INPUT grid. An OUTPUT dump is a different
            # shape whenever the kernel shrinks the frame — a 3x3 Sobel over
            # 32x32 with no padding yields 30x30 — and forcing those 900 values
            # into a 32x32 grid shears every row 2 pixels further left, turning
            # the edge map into a diagonal smear. Trust the marker only when the
            # value count actually fits it.
            if n > 0 and count in (n * n, 3 * n * n):
                return n
        except (OSError, ValueError):
            pass
    if count >= 3 and max_val <= 255:
        rgb_side = int(math.isqrt(count // 3))
        if rgb_side * rgb_side * 3 == count:
            return rgb_side
    side = int(math.isqrt(count))
    return side if side > 0 else 0


def render_mem_image(mem_path: Path, out_png: Path, size: int = 0,
                     workspace: Optional[Path] = None) -> bool:
    """Render a hex .mem dump to a PNG (upscaled, nearest-neighbour). Returns
    True on success; never raises — a missing preview must not fail a stage."""
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001 — no pillow → no preview, not an error
        return False
    try:
        mem_path, out_png = Path(mem_path), Path(out_png)
        vals = read_values(mem_path)
        if not vals:
            return False
        n, mx = len(vals), max(vals)
        if not size:
            size = infer_size(workspace or mem_path.parent.parent, n, mx)
        if size < 2:
            return False

        k = size * size
        img = Image.new("RGB", (size, size))
        px = img.load()

        if n >= 3 * k and mx <= 255:                       # interleaved R,G,B bytes
            for i in range(k):
                r, g, b = vals[3 * i], vals[3 * i + 1], vals[3 * i + 2]
                px[i % size, i // size] = (r & 255, g & 255, b & 255)
        elif n >= k and mx > 255:                          # packed 24-bit words
            for i in range(k):
                v = vals[i]
                px[i % size, i // size] = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
        elif mx <= 9:                                      # categorical grid
            # A fixed palette, not a grayscale autoscale: autoscaling made the
            # cell values (and the computed PATH) illegible.
            padded = vals + [0] * k
            for i in range(k):
                px[i % size, i // size] = _PALETTE[max(0, min(9, padded[i]))]
        else:                                              # grayscale, autoscaled
            padded = vals + [0] * k
            scale = 255.0 / (mx or 1)
            for i in range(k):
                g = int(padded[i] * scale)
                px[i % size, i // size] = (g, g, g)

        out_png.parent.mkdir(parents=True, exist_ok=True)
        img.resize((256, 256), Image.NEAREST).save(out_png)
        return True
    except Exception:  # noqa: BLE001
        return False


__all__ = ["render_mem_image", "infer_size", "read_values"]
