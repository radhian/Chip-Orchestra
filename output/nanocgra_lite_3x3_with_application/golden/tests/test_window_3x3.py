"""Test window_3x3 — 3x3 window assembler."""
from model.window_3x3 import Window3x3
from model.params import IMG_W

def test_reset():
    w = Window3x3()
    w.reset()
    assert w.win == [0] * 9
    assert w.window_valid == 0

def test_window_forms_after_3x3():
    """Feed a 3x3 region with known values, check window contents."""
    w = Window3x3()
    w.reset()
    # Feed 3 rows x 3 cols.  Use value = row*10+col for traceability.
    for row in range(3):
        for col in range(3):
            pixel = row * 10 + col
            lb0 = (row - 2) * 10 + col if row >= 2 else 0
            lb1 = (row - 1) * 10 + col if row >= 1 else 0
            win, valid = w.step(1, 1, 1, pixel, lb0, lb1, col, row)
    assert valid == 1
    # window should be:
    # row0: 0,1,2  row1: 10,11,12  row2: 20,21,22
    assert win == [0, 1, 2, 10, 11, 12, 20, 21, 22]

def test_not_valid_before_3x3():
    w = Window3x3()
    w.reset()
    # feed 2 rows only
    for row in range(2):
        for col in range(3):
            pixel = row * 10 + col
            lb1 = (row - 1) * 10 + col if row >= 1 else 0
            win, valid = w.step(1, 1, 1, pixel, 0, lb1, col, row)
            assert valid == 0