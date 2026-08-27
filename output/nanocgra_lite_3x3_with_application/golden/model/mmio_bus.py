"""mmio_bus — 8-bit MMIO interconnect / address decoder.

Hardware: rtl/mmio_bus.v
Ports (name, dir, width):
  clk          input  1
  rst_n        input  1
  mst_addr     input  8
  mst_wr       input  1
  mst_rd       input  1
  mst_wdata    input  8
  mst_rdata    output 8
  sram_sel     output 1
  uart_sel     output 1
  cgra_sel     output 1
  sram_addr    output 5
  sram_wr_en   output 1
  sram_wdata   output 8
  sram_rdata   input  8
  uart_rdata   input  8
  cgra_rdata   input  8

Address map:
  0x00-0x1F : SRAM
  0x80-0x83 : UART regs
  0x90-0x9B : CGRA config/operands
  0xA0      : START
  0xA1      : STATUS
"""

from .params import (ADDR_SRAM_BASE, ADDR_UART_TXDATA, ADDR_CGRA_CFG_BASE,
                     ADDR_START, ADDR_STATUS)

class MMIOBus:
    def __init__(self):
        self.mst_rdata = 0
        self.sram_sel = 0
        self.uart_sel = 0
        self.cgra_sel = 0
        self.sram_addr = 0
        self.sram_wr_en = 0
        self.sram_wdata = 0

    def reset(self):
        self.mst_rdata = 0
        self.sram_sel = 0
        self.uart_sel = 0
        self.cgra_sel = 0
        self.sram_addr = 0
        self.sram_wr_en = 0
        self.sram_wdata = 0

    def step(self, clk, rst_n, mst_addr, mst_wr, mst_rd, mst_wdata,
             sram_rdata, uart_rdata, cgra_rdata):
        if not rst_n:
            self.reset()
            return self._outputs()
        a = int(mst_addr) & 0xFF
        self.sram_sel = 1 if (a & 0xE0) == 0x00 and a <= 0x1F else 0
        self.uart_sel = 1 if 0x80 <= a <= 0x83 else 0
        self.cgra_sel = 1 if 0x90 <= a <= 0x9B or a == ADDR_START else 0
        self.sram_addr = a & 0x1F
        self.sram_wr_en = 1 if (self.sram_sel and mst_wr) else 0
        self.sram_wdata = int(mst_wdata) & 0xFF
        # read mux
        rdata = 0
        if self.sram_sel:   rdata = sram_rdata
        elif self.uart_sel: rdata = uart_rdata
        elif self.cgra_sel: rdata = cgra_rdata
        self.mst_rdata = rdata & 0xFF
        return self._outputs()

    def _outputs(self):
        return {
            'mst_rdata': self.mst_rdata,
            'sram_sel': self.sram_sel,
            'uart_sel': self.uart_sel,
            'cgra_sel': self.cgra_sel,
            'sram_addr': self.sram_addr,
            'sram_wr_en': self.sram_wr_en,
            'sram_wdata': self.sram_wdata,
        }