"""baud_gen — baud-rate tick generator.

Hardware: rtl/baud_gen.v
Ports (name, dir, width):
  clk        input  1
  rst_n      input  1
  baud_tick  output 1   (1-cycle pulse once per bit period)

The divider counts CLK_FREQ/BAUD_RATE clocks and emits a 1-cycle tick.
"""

from .params import CLK_FREQ, BAUD_RATE

class BaudGen:
    def __init__(self):
        self.div = max(1, CLK_FREQ // BAUD_RATE)  # ticks per bit
        self.cnt = 0

    def reset(self):
        self.cnt = 0

    def step(self, clk, rst_n):
        """Advance one clock. Returns baud_tick (1-cycle pulse)."""
        tick = 0
        if clk and rst_n:
            if self.cnt == self.div - 1:
                self.cnt = 0
                tick = 1
            else:
                self.cnt += 1
        return tick