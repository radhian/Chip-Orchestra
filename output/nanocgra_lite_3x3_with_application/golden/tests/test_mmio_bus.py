"""Test mmio_bus — 8-bit MMIO interconnect / address decoder."""
from model.mmio_bus import MMIOBus
from model.params import ADDR_SRAM_BASE, ADDR_UART_TXDATA, ADDR_CGRA_CFG_BASE, ADDR_START

def test_reset():
    bus = MMIOBus()
    bus.reset()
    assert bus.mst_rdata == 0

def test_sram_select():
    bus = MMIOBus()
    o = bus.step(1, 1, 0x10, 0, 1, 0, 0x42, 0, 0)
    assert o['sram_sel'] == 1
    assert o['uart_sel'] == 0
    assert o['cgra_sel'] == 0
    assert o['mst_rdata'] == 0x42

def test_uart_select():
    bus = MMIOBus()
    o = bus.step(1, 1, ADDR_UART_TXDATA, 0, 1, 0, 0, 0x55, 0)
    assert o['uart_sel'] == 1
    assert o['mst_rdata'] == 0x55

def test_cgra_select():
    bus = MMIOBus()
    o = bus.step(1, 1, ADDR_CGRA_CFG_BASE, 0, 1, 0, 0, 0, 0x77)
    assert o['cgra_sel'] == 1
    assert o['mst_rdata'] == 0x77

def test_start_addr():
    bus = MMIOBus()
    o = bus.step(1, 1, ADDR_START, 1, 0, 0x01, 0, 0, 0)
    assert o['cgra_sel'] == 1

def test_sram_write():
    bus = MMIOBus()
    o = bus.step(1, 1, 0x05, 1, 0, 0xAB, 0, 0, 0)
    assert o['sram_wr_en'] == 1
    assert o['sram_addr'] == 5
    assert o['sram_wdata'] == 0xAB