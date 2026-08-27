"""Test sobel_core — Sobel Gx/Gy + magnitude."""
from model.sobel_core import sobel_compute

def test_flat_region():
    """Uniform region => zero gradient."""
    w = [100] * 9
    gx, gy, out = sobel_compute(w)
    assert gx == 0
    assert gy == 0
    assert out == 0

def test_vertical_edge():
    """Left half 0, right half 255 => strong Gx."""
    w = [0, 0, 255,
         0, 0, 255,
         0, 0, 255]
    gx, gy, out = sobel_compute(w)
    # Gx = -0+255 -0+2*255 -0+255 = 255+510+255 = 1020
    assert gx == 1020
    assert gy == 0
    assert out == 255  # saturated

def test_horizontal_edge():
    """Top half 0, bottom half 255 => strong Gy."""
    w = [0, 0, 0,
         0, 0, 0,
         255, 255, 255]
    gx, gy, out = sobel_compute(w)
    assert gx == 0
    assert gy == 1020
    assert out == 255

def test_hand_computed():
    """Hand-computed example with distinct values."""
    w = [10, 20, 30,
         40, 50, 60,
         70, 80, 90]
    # Gx = -10+30 -2*40+2*60 -70+90 = 20 + 40 + 20 = 80
    # Gy = -10-2*20-30 +70+2*80+90 = -90 + 330 = 240
    gx, gy, out = sobel_compute(w)
    assert gx == 80
    assert gy == 240
    assert out == 255  # 80+240=320 > 255

def test_no_saturation():
    w = [10, 20, 30,
         40, 50, 60,
         70, 80, 90]
    # use a case where |Gx|+|Gy| < 255
    w2 = [5, 10, 15,
          10, 15, 20,
          15, 20, 25]
    gx, gy, out = sobel_compute(w2)
    # Gx = -5+15 -2*10+2*20 -15+25 = 10+20+10 = 40
    # Gy = -5-2*10-15 +15+2*20+25 = -40 + 80 = 40
    assert gx == 40
    assert gy == 40
    assert out == 80