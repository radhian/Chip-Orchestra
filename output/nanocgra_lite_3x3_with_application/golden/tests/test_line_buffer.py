"""Test line_buffer — 32-byte shift register."""
from model.line_buffer import LineBuffer
from model.params import LINE_BUF_W

def test_reset_clears():
    lb = LineBuffer()
    lb.row = [0xFF] * LINE_BUF_W
    lb.step(1, 0, 0, 0)
    assert all(v == 0 for v in lb.row)

def test_shift_in():
    lb = LineBuffer()
    lb.reset()
    for i in range(LINE_BUF_W):
        lb.step(1, 1, 1, i + 1)
    assert lb.row == list(range(1, LINE_BUF_W + 1))

def test_overflow():
    lb = LineBuffer()
    lb.reset()
    for i in range(LINE_BUF_W + 5):
        lb.step(1, 1, 1, i)
    # last LINE_BUF_W values should be 5..LINE_BUF_W+4
    assert lb.row == list(range(5, LINE_BUF_W + 5))

def test_no_shift_when_disabled():
    lb = LineBuffer()
    lb.reset()
    lb.step(1, 1, 1, 42)
    lb.step(1, 1, 0, 99)
    assert lb.row[-1] == 42