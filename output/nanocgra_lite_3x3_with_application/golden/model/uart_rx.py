"""uart_rx — UART receiver (serial -> byte).

Hardware: rtl/uart_rx.v
Ports (name, dir, width):
  clk       input  1
  rst_n     input  1
  rx_in     input  1   (serial line, idle high)
  rx_byte   output 8   (received data byte)
  rx_valid  output 1   (1-cycle pulse when byte is ready)

Frame: 1 start bit (0), 8 data bits LSB-first, 1 stop bit (1).
Sampling: the model samples at the baud tick.  It waits for a falling
edge (start), then samples 8 data bits at successive baud ticks, then
the stop bit.  rx_valid pulses for one cycle when the full byte arrives.
"""

from .baud_gen import BaudGen

class UartRx:
    START, DATA, STOP = 0, 1, 2

    def __init__(self):
        self.bg = BaudGen()
        self.state = self.STOP
        self.bit_idx = 0
        self.shreg = 0
        self.rx_byte = 0
        self.rx_valid = 0
        self._prev_line = 1

    def reset(self):
        self.bg.reset()
        self.state = self.STOP
        self.bit_idx = 0
        self.shreg = 0
        self.rx_byte = 0
        self.rx_valid = 0
        self._prev_line = 1

    def step(self, clk, rst_n, rx_in):
        """Advance one clock. Returns (rx_byte, rx_valid)."""
        self.rx_valid = 0
        tick = self.bg.step(clk, rst_n)
        if not rst_n:
            self.reset()
            return self.rx_byte, self.rx_valid
        if not tick:
            return self.rx_byte, self.rx_valid

        if self.state == self.STOP:
            # detect start bit (falling edge to 0)
            if self._prev_line == 1 and rx_in == 0:
                self.state = self.DATA
                self.bit_idx = 0
                self.shreg = 0
        elif self.state == self.DATA:
            # sample data bit (LSB first)
            self.shreg |= (1 if rx_in else 0) << self.bit_idx
            self.bit_idx += 1
            if self.bit_idx == 8:
                self.rx_byte = self.shreg & 0xFF
                self.state = self.STOP
                self.rx_valid = 1
        self._prev_line = rx_in
        return self.rx_byte, self.rx_valid