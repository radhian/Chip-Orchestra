"""Test baud_gen — baud rate tick generator."""
from model.baud_gen import BaudGen
from model.params import CLK_FREQ, BAUD_RATE

def test_tick_period():
    bg = BaudGen()
    bg.reset()
    div = CLK_FREQ // BAUD_RATE
    ticks = []
    for _ in range(div * 3):
        ticks.append(bg.step(1, 1))
    # exactly 3 ticks in 3*div cycles
    assert sum(ticks) == 3

def test_no_tick_in_reset():
    bg = BaudGen()
    bg.reset()
    for _ in range(1000):
        assert bg.step(1, 0) == 0