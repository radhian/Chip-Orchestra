"""Test sram_32b — 32-byte single-port SRAM."""
from model.sram_32b import SRAM32B

def test_reset():
    s = SRAM32B()
    s.mem = [0xFF] * 32
    s.step(1, 0, 0, 0, 0)
    assert all(v == 0 for v in s.mem)

def test_write_read():
    s = SRAM32B()
    s.reset()
    s.step(1, 1, 5, 1, 0xAB)
    assert s.read(5) == 0xAB
    s.step(1, 1, 5, 0, 0)
    assert s.read(5) == 0xAB

def test_all_addresses():
    s = SRAM32B()
    s.reset()
    for a in range(32):
        s.step(1, 1, a, 1, a * 2)
    for a in range(32):
        assert s.read(a) == (a * 2) & 0xFF