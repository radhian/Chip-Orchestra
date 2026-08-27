"""Test top — toplevel golden model end-to-end on canonical input."""
import json, os
from model.top import sobel_stream, sobel_array
from model.sobel_core import sobel_compute
from model.params import IMG_W, IMG_H, OUT_W, OUT_H

def _load_input():
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'context', 'chip_input_grid.json')
    with open(path) as f:
        data = json.load(f)
    return data['pixels']  # 2D list

def test_output_size():
    pixels_2d = _load_input()
    flat = [p for row in pixels_2d for p in row]
    out = sobel_stream(flat)
    assert len(out) == OUT_W * OUT_H

def test_matches_reference_sobel():
    """Compare streaming model against a direct 2D Sobel reference."""
    pixels_2d = _load_input()
    flat = [p for row in pixels_2d for p in row]
    out = sobel_stream(flat)
    # direct reference
    ref = []
    for y in range(OUT_H):
        for x in range(OUT_W):
            w = [pixels_2d[y + r][x + c] for r in range(3) for c in range(3)]
            _, _, o = sobel_compute(w)
            ref.append(o)
    assert out == ref, f"streaming model mismatch with reference"

def test_known_value():
    """Spot-check one output pixel against a hand/loop computation."""
    pixels_2d = _load_input()
    flat = [p for row in pixels_2d for p in row]
    out = sobel_stream(flat)
    # recompute pixel (0,0) directly
    w = [pixels_2d[r][c] for r in range(3) for c in range(3)]
    _, _, expected = sobel_compute(w)
    assert out[0] == expected

def test_all_bytes_valid():
    pixels_2d = _load_input()
    flat = [p for row in pixels_2d for p in row]
    out = sobel_stream(flat)
    assert all(0 <= v <= 255 for v in out)