"""line_buffer — 32-byte shift register storing one image row.

Hardware: rtl/line_buffer.v
Ports (name, dir, width):
  clk        input  1
  rst_n      input  1
  shift_en   input  1
  pixel_in   input  8
  row_out    output 8*LINE_BUF_W  (whole row, [0]=oldest .. [W-1]=newest)

Behaviour: on each shift_en pulse the incoming pixel is pushed in at
the right (newest) end and the oldest pixel falls off the left.
row_out exposes the full row so the window assembler can tap any column.
"""

from .params import LINE_BUF_W

class LineBuffer:
    def __init__(self, width=LINE_BUF_W):
        self.width = width
        self.row = [0] * width

    def reset(self):
        self.row = [0] * self.width

    def step(self, clk, rst_n, shift_en, pixel_in):
        if not rst_n:
            self.reset()
            return list(self.row)
        if clk and shift_en:
            # shift left, push new pixel at right
            self.row = self.row[1:] + [int(pixel_in) & 0xFF]
        return list(self.row)

    def tap(self, col):
        """Read column value (0=oldest .. width-1=newest)."""
        return self.row[col] & 0xFF