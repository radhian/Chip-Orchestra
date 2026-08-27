"""uart_tx — UART transmitter (byte -> serial).

Hardware: rtl/uart_tx.v
Ports (name, dir, width):
  clk       input  1
  rst_n     input  1
  tx_start  input  1   (pulse: load data_in and begin transmission)
  data_in   input  8   (byte to transmit)
  tx_out    output 1   (serial line, idle high)
  tx_done   output 1   (1-cycle pulse when stop bit finishes)

Frame: 1 start bit (0), 8 data bits LSB-first, 1 stop bit (1).

tx_start is LATCHED when it arrives (on any clock, not only on a baud
tick) so that a 1-cycle request pulse is never dropped.  The latched
request is consumed on the next baud tick.

Back-to-back frames: when the STOP bit ends, if start_req is already
set (pre-armed during the current frame), the FSM transitions directly
STOP->START instead of STOP->IDLE->START.  This eliminates the 1-baud
IDLE gap so the TX frame cycle is exactly 10 baud periods.
"""

from .baud_gen import BaudGen

class UartTx:
    IDLE, START, DATA, STOP = 0, 1, 2, 3

    def __init__(self):
        self.bg = BaudGen()
        self.state = self.IDLE
        self.bit_idx = 0
        self.shreg = 0
        self.tx_out = 1
        self.tx_done = 0
        self.start_req = 0
        self.start_data = 0

    def reset(self):
        self.bg.reset()
        self.state = self.IDLE
        self.bit_idx = 0
        self.shreg = 0
        self.tx_out = 1
        self.tx_done = 0
        self.start_req = 0
        self.start_data = 0

    def step(self, clk, rst_n, tx_start, data_in):
        """Advance one clock. Returns (tx_out, tx_done)."""
        self.tx_done = 0
        # LATCH tx_start on ANY clock (not only on baud tick) so a
        # 1-cycle request pulse is never dropped.
        if clk and rst_n and tx_start:
            self.start_req = 1
            self.start_data = int(data_in) & 0xFF
        tick = self.bg.step(clk, rst_n)
        if not rst_n:
            self.reset()
            return self.tx_out, self.tx_done
        if not tick:
            return self.tx_out, self.tx_done

        if self.state == self.IDLE:
            if self.start_req:
                self.shreg = self.start_data
                self.bit_idx = 0
                self.state = self.START
                self.tx_out = 0          # begin start bit
                self.start_req = 0
            else:
                self.tx_out = 1
        elif self.state == self.START:
            # start-bit period is over; emit first data bit (bit 0)
            self.tx_out = (self.shreg >> 0) & 1
            self.bit_idx = 1
            self.state = self.DATA
        elif self.state == self.DATA:
            self.tx_out = (self.shreg >> self.bit_idx) & 1
            self.bit_idx += 1
            if self.bit_idx == 8:
                self.state = self.STOP
        elif self.state == self.STOP:
            self.tx_out = 1
            self.tx_done = 1
            # Back-to-back: if start_req is already set (pre-armed
            # during this frame), go directly to START — no IDLE gap.
            if self.start_req:
                self.shreg = self.start_data
                self.bit_idx = 0
                self.state = self.START
                self.tx_out = 0          # begin next start bit
                self.start_req = 0
            else:
                self.state = self.IDLE
        return self.tx_out, self.tx_done
