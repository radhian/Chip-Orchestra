"""Test pe — single Processing Element."""
from model.pe import PE

def test_reset():
    pe = PE()
    pe.reset()
    assert pe.result == 0

def test_pass():
    pe = PE()
    r, _ = pe.step(1, 1, PE.PASS, 0x53, 0)
    assert r == 0x53

def test_zero():
    pe = PE()
    r, _ = pe.step(1, 1, PE.ZERO, 0xFF, 0)
    assert r == 0

def test_shl1():
    pe = PE()
    r, _ = pe.step(1, 1, PE.SHL1, 0x10, 0)
    assert r == 0x20

def test_shl1_overflow():
    pe = PE()
    r, _ = pe.step(1, 1, PE.SHL1, 0x80, 0)
    assert r == 0x00  # 0x80<<1 = 0x100, truncated to 8 bits

def test_neg():
    pe = PE()
    r, _ = pe.step(1, 1, PE.NEG, 0x05, 0)
    assert r == (-5 & 0xFF) == 0xFB

def test_neg_shl1():
    pe = PE()
    r, _ = pe.step(1, 1, PE.NEG_SHL1, 0x03, 0)
    assert r == (-6 & 0xFF) == 0xFA

def test_abs():
    pe = PE()
    # abs treats input as signed: 0xFB = -5 -> 5
    r, _ = pe.step(1, 1, PE.ABS, 0xFB, 0)
    assert r == 5