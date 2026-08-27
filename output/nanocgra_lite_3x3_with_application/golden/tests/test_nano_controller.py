"""Test nano_controller — FSM sequencer."""
from model.nano_controller import NanoController
from model.params import IMG_W, IMG_H, OUT_W, OUT_H

def test_reset():
    c = NanoController()
    c.reset()
    assert c.state == NanoController.S_IDLE

def test_idle_to_recv():
    c = NanoController()
    c.reset()
    o = c.step(1, 1, 0x42, 1, 0, 0, 0)
    assert c.state == NanoController.S_RECV
    assert o['pixel_in'] == 0x42
    assert o['pixel_shift'] == 1

def test_pixel_counting():
    c = NanoController()
    c.reset()
    for i in range(5):
        c.step(1, 1, i, 1, 0, 0, 0)
    assert c.pixel_cnt == 5
    assert c.col_cnt == 5
    assert c.row_cnt == 0

def test_row_advance():
    c = NanoController()
    c.reset()
    for i in range(IMG_W + 3):
        c.step(1, 1, i, 1, 0, 0, 0)
    assert c.row_cnt == 1
    assert c.col_cnt == 3