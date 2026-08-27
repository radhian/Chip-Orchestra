"""nano_controller — microcoded FSM sequencer.

Hardware: rtl/nano_controller.v
Ports (name, dir, width):
  clk          input  1
  rst_n        input  1
  rx_byte      input  8
  rx_valid     input  1
  tx_done      input  1
  cgra_done    input  1
  sobel_out    input  8
  bus_addr     output 8
  bus_wr       output 1
  bus_rd       output 1
  bus_wdata    output 8
  pixel_in     output 8    (pixel fed to line buffer / window)
  pixel_shift  output 1    (shift enable to line buffers / window)
  col_cnt      output 6
  row_cnt      output 6
  start_cgra   output 1
  tx_start     output 1
  tx_data      output 8
  status       output 8    ({6'b0, done, busy})

FSM:
  S_IDLE      — wait for first rx_valid
  S_RECV      — stream pixels in; after row>=2 & col>=2, compute Sobel
  S_COMPUTE   — latch window, run CGRA (1-cycle)
  S_TX_RESULT — send result byte via UART TX
  S_NEXT      — advance to next window; if all 30x30 done -> S_IDLE

Streaming: the controller does NOT buffer the full frame.  Each arriving
pixel is shifted into the line-buffer chain; whenever a valid 3x3 window
exists the Sobel result is computed and emitted immediately.
"""

from .params import IMG_W, IMG_H, OUT_W, OUT_H

class NanoController:
    S_IDLE = 0
    S_RECV = 1
    S_COMPUTE = 2
    S_TX_RESULT = 3
    S_NEXT = 4

    def __init__(self):
        self.state = self.S_IDLE
        self.col_cnt = 0
        self.row_cnt = 0
        self.pixel_cnt = 0
        self.out_cnt = 0
        self.bus_addr = 0
        self.bus_wr = 0
        self.bus_rd = 0
        self.bus_wdata = 0
        self.pixel_in = 0
        self.pixel_shift = 0
        self.start_cgra = 0
        self.tx_start = 0
        self.tx_data = 0
        self.status = 0
        self._result = 0
        self._pending_tx = False

    def reset(self):
        self.state = self.S_IDLE
        self.col_cnt = 0
        self.row_cnt = 0
        self.pixel_cnt = 0
        self.out_cnt = 0
        self.bus_addr = 0
        self.bus_wr = 0
        self.bus_rd = 0
        self.bus_wdata = 0
        self.pixel_in = 0
        self.pixel_shift = 0
        self.start_cgra = 0
        self.tx_start = 0
        self.tx_data = 0
        self.status = 0
        self._result = 0
        self._pending_tx = False

    def step(self, clk, rst_n, rx_byte, rx_valid, tx_done, cgra_done, sobel_out):
        if not rst_n:
            self.reset()
            return self._outputs()
        # default pulses
        self.pixel_shift = 0
        self.start_cgra = 0
        self.tx_start = 0
        self.bus_wr = 0
        self.bus_rd = 0

        if self.state == self.S_IDLE:
            if rx_valid:
                self.state = self.S_RECV
                self.col_cnt = 0
                self.row_cnt = 0
                self.pixel_cnt = 0
                self.out_cnt = 0
                self._accept_pixel(rx_byte)
        elif self.state == self.S_RECV:
            if rx_valid:
                self._accept_pixel(rx_byte)
                # after accepting, check if a valid window exists
                if self.row_cnt >= 2 and self.col_cnt >= 2:
                    self._result = int(sobel_out) & 0xFF
                    self.state = self.S_TX_RESULT
                    self._pending_tx = True
        elif self.state == self.S_TX_RESULT:
            self.tx_data = self._result & 0xFF
            self.tx_start = 1
            self.state = self.S_NEXT
        elif self.state == self.S_NEXT:
            if tx_done:
                self.out_cnt += 1
                if self.out_cnt >= OUT_W * OUT_H:
                    self.state = self.S_IDLE
                    self.status = 0x02  # done
                else:
                    self.state = self.S_RECV
        return self._outputs()

    def _accept_pixel(self, byte):
        self.pixel_in = int(byte) & 0xFF
        self.pixel_shift = 1
        self.pixel_cnt += 1
        self.col_cnt = self.pixel_cnt % IMG_W
        self.row_cnt = self.pixel_cnt // IMG_W

    def _outputs(self):
        return {
            'bus_addr': self.bus_addr,
            'bus_wr': self.bus_wr,
            'bus_rd': self.bus_rd,
            'bus_wdata': self.bus_wdata,
            'pixel_in': self.pixel_in,
            'pixel_shift': self.pixel_shift,
            'col_cnt': self.col_cnt,
            'row_cnt': self.row_cnt,
            'start_cgra': self.start_cgra,
            'tx_start': self.tx_start,
            'tx_data': self.tx_data,
            'status': self.status,
            'state': self.state,
        }