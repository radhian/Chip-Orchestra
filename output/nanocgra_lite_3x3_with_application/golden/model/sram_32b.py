"""sram_32b — 32-byte single-port SRAM.

Hardware: rtl/sram_32b.v
Ports (name, dir, width):
  clk       input  1
  addr      input  5
  wr_en     input  1
  data_in   input  8
  data_out  output 8

Single-port: read or write on the same cycle (write takes priority,
read returns the old value on a write, new value on a read).
"""

class SRAM32B:
    SIZE = 32

    def __init__(self):
        self.mem = [0] * self.SIZE
        self.data_out = 0

    def reset(self):
        self.mem = [0] * self.SIZE
        self.data_out = 0

    def step(self, clk, rst_n, addr, wr_en, data_in):
        if not rst_n:
            self.reset()
            return self.data_out
        a = int(addr) & 0x1F
        if clk:
            if wr_en:
                self.mem[a] = int(data_in) & 0xFF
            self.data_out = self.mem[a] & 0xFF
        return self.data_out

    def read(self, addr):
        return self.mem[int(addr) & 0x1F] & 0xFF

    def write(self, addr, val):
        self.mem[int(addr) & 0x1F] = int(val) & 0xFF