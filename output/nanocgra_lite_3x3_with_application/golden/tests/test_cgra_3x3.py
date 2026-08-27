"""Test cgra_3x3 — 3x3 PE mesh Sobel compute."""
from model.cgra_3x3 import CGRA3x3
from model.sobel_core import sobel_compute

def test_reset():
    cgra = CGRA3x3()
    cgra.reset()
    assert cgra.sobel_out == 0

def test_flat():
    cgra = CGRA3x3()
    w = [100] * 9
    out, done = cgra.step(1, 1, w, 1)
    assert out == 0
    assert done == 1

def test_vertical_edge():
    cgra = CGRA3x3()
    w = [0, 0, 255,
         0, 0, 255,
         0, 0, 255]
    out, done = cgra.step(1, 1, w, 1)
    gx, gy, expected = sobel_compute(w)
    assert out == expected == 255

def test_matches_sobel_core():
    """CGRA output must match sobel_core for several windows."""
    import random
    random.seed(42)
    cgra = CGRA3x3()
    for _ in range(20):
        w = [random.randint(0, 255) for _ in range(9)]
        out, _ = cgra.step(1, 1, w, 1)
        _, _, expected = sobel_compute(w)
        assert out == expected, f"win={w} cgra={out} expected={expected}"