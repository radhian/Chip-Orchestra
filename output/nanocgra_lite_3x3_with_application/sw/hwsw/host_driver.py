#!/usr/bin/env python3
"""host_driver.py — the SOFTWARE side of the chip's interface (generated).

This is the program a host would run to use the accelerator. It knows three
things about the hardware, all read off the top-level RTL:

  * the sample format   : 8-bit values
  * the input geometry  : 32x32
  * the output geometry : 30x30

`encode` turns a user file (an image, or a raw/hex byte dump) into the exact
byte stream the chip expects and ALSO computes what the Python golden model
says the answer should be, so the run is checkable. `decode` turns the bytes
the chip sent back into a picture and compares them value-for-value.

Run from the workspace root:
    python3 sw/hwsw/host_driver.py encode --input <file>
    python3 sw/hwsw/host_driver.py decode
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

IMG_W, IMG_H = 32, 32
OUT_W, OUT_H = 30, 30
SAMPLE_MAX = 255

ROOT = Path(__file__).resolve().parents[2]
STIMULUS = ROOT / "hwsw/stimulus.mem"
EXPECTED = ROOT / "hwsw/expected_output.mem"
CHIP = ROOT / "hwsw/chip_output.mem"
ENCODE_JSON = ROOT / "hwsw/encode.json"
VERIFY_JSON = ROOT / "hwsw/verify.json"


# ----------------------------------------------------------------- utilities
def _read_mem(path: Path):
    """Hex tokens of a .mem file (skipping comments and @address directives)."""
    values = []
    try:
        body = path.read_text(errors="replace")
    except OSError:
        return values
    for line in body.splitlines():
        line = line.split("//")[0]
        for token in line.split():
            if token.startswith("@"):
                continue
            try:
                values.append(int(token, 16))
            except ValueError:
                pass
    return values


def _write_mem(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{v & SAMPLE_MAX:02x}" for v in values) + "\n")


def _save_png(values, width: int, height: int, path: Path) -> bool:
    """Render a flat sample list as a grayscale picture, upscaled so a 30x30
    result is actually visible in a browser."""
    try:
        from PIL import Image
    except Exception:
        return False
    if width <= 0 or height <= 0:
        return False
    padded = list(values[: width * height]) + [0] * max(0, width * height - len(values))
    image = Image.new("L", (width, height))
    image.putdata([max(0, min(255, int(v))) for v in padded])
    scale = max(1, 320 // max(width, height))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((width * scale, height * scale), Image.NEAREST).save(path)
    return True


def _load_samples(source: Path):
    """A user file -> the flat sample list the chip consumes."""
    suffix = source.suffix.lower()
    if suffix in {".mem", ".hex"}:
        return _read_mem(source)
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}:
        from PIL import Image
        image = Image.open(source).convert("L")
        if IMG_W and IMG_H:
            image = image.resize((IMG_W, IMG_H), Image.LANCZOS)
        return list(image.getdata())
    if suffix in {".txt", ".csv"}:
        text = source.read_text(errors="replace").replace(",", " ")
        return [int(float(tok)) for tok in text.split() if tok.strip("+-.").replace(".", "").isdigit()]
    return list(source.read_bytes())


# ------------------------------------------------------------- golden model
def _golden(samples):
    """Run the approved Python reference on the same input, if it exposes a
    whole-frame entry point. Returns (values, note) — an empty list simply means
    the run is unchecked and the reviewer's eyes are the verdict."""
    sys.path.insert(0, str(ROOT / "golden"))
    sys.path.insert(0, str(ROOT))
    try:
        from model import top as golden_top
    except Exception as exc:
        return [], f"golden model not importable ({exc})"
    expected_len = OUT_W * OUT_H if OUT_W and OUT_H else 0
    names = [n for n in dir(golden_top) if not n.startswith("_") and callable(getattr(golden_top, n))]
    names.sort(key=lambda n: 0 if any(k in n.lower() for k in
               ("stream", "process", "run", "top", "compute", "forward", "apply")) else 1)
    for name in names:
        try:
            result = getattr(golden_top, name)(list(samples))
        except Exception:
            continue
        try:
            values = [int(v) for v in result]
        except Exception:
            continue
        if values and (not expected_len or len(values) == expected_len):
            return values, f"golden/model/top.py::{name}"
    return [], "no whole-frame entry point found in golden/model/top.py"


# ----------------------------------------------------------------- commands
def cmd_encode(args) -> int:
    source = Path(args.input)
    if not source.is_absolute():
        source = ROOT / source
    samples = _load_samples(source)
    if IMG_W and IMG_H:
        need = IMG_W * IMG_H
        samples = (list(samples) + [0] * need)[:need]
    _write_mem(STIMULUS, samples)
    _save_png(samples, IMG_W, IMG_H, ROOT / "hwsw" / "input_preview.png")

    expected, note = _golden(samples)
    if expected:
        _write_mem(EXPECTED, expected)
        _save_png(expected, OUT_W or IMG_W, OUT_H or IMG_H, ROOT / "hwsw" / "expected_output.png")

    payload = {
        "input": str(source.relative_to(ROOT)) if str(source).startswith(str(ROOT)) else str(source),
        "bytes_in": len(samples),
        "bytes_out": len(expected) if expected else (OUT_W * OUT_H if OUT_W and OUT_H else 0),
        "in_geometry": [IMG_W, IMG_H],
        "out_geometry": [OUT_W, OUT_H],
        "golden": note,
        "golden_available": bool(expected),
    }
    ENCODE_JSON.parent.mkdir(parents=True, exist_ok=True)
    ENCODE_JSON.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


def cmd_decode(args) -> int:
    chip = _read_mem(CHIP)
    expected = _read_mem(EXPECTED)
    _save_png(chip, OUT_W or IMG_W, OUT_H or IMG_H, ROOT / "hwsw" / "chip_output.png")

    mismatches = 0
    first = None
    max_diff = 0
    if expected and chip:
        for index in range(min(len(expected), len(chip))):
            if chip[index] != expected[index]:
                mismatches += 1
                max_diff = max(max_diff, abs(chip[index] - expected[index]))
                if first is None:
                    first = {"index": index, "chip": chip[index], "expected": expected[index]}
        mismatches += abs(len(expected) - len(chip))

    payload = {
        "bytes_received": len(chip),
        "bytes_expected": len(expected),
        "checked": bool(expected and chip),
        "match": bool(expected and chip and mismatches == 0 and len(chip) >= len(expected)),
        "mismatches": mismatches,
        "first_mismatch": first,
        "max_abs_diff": max_diff,
    }
    VERIFY_JSON.parent.mkdir(parents=True, exist_ok=True)
    VERIFY_JSON.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Host driver for the generated chip")
    sub = parser.add_subparsers(dest="command", required=True)
    encode = sub.add_parser("encode", help="user file -> chip byte stream + expected answer")
    encode.add_argument("--input", required=True)
    encode.add_argument("--outdir", default="hwsw")
    encode.set_defaults(func=cmd_encode)
    decode = sub.add_parser("decode", help="chip bytes -> picture + comparison")
    decode.add_argument("--outdir", default="hwsw")
    decode.set_defaults(func=cmd_decode)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
