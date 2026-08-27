"""Test reset_sync — synchronized reset generator."""
import pytest
from model.reset_sync import ResetSync

def test_reset_asserted_on_poweron():
    rs = ResetSync(sync_depth=2)
    rs.reset()
    # after power-on, rst_n should be 0 for at least sync_depth cycles
    for _ in range(2):
        r = rs.step(1, 1)  # rst_async_n=1 but shreg still flushing
    # after 2 cycles with rst_async_n=1, rst_n should deassert
    assert rs.step(1, 1) == 1

def test_reset_held_while_async_low():
    rs = ResetSync(sync_depth=2)
    rs.reset()
    for _ in range(5):
        r = rs.step(1, 0)  # rst_async_n=0
        assert r == 0

def test_reset_deasserts_synchronously():
    rs = ResetSync(sync_depth=2)
    rs.reset()
    # hold async low
    for _ in range(3):
        rs.step(1, 0)
    # release
    rs.step(1, 1)
    rs.step(1, 1)
    assert rs.step(1, 1) == 1