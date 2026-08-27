"""window_3x3 — assembles a 3x3 window from 2 line buffers + current pixel.

Hardware: rtl/window_3x3.v
Ports (name, dir, width):
  clk            input  1
  rst_n          input  1
  pixel_in       input  8    (current arriving pixel, row N)
  shift_en       input  1
  lb0_data       input  8    (row N-2 pixel at current column)
  lb1_data       input  8    (row N-1 pixel at current column)
  col_cnt        input  6    (current column 0..IMG_W-1)
  row_cnt        input  6    (current row 0..IMG_H-1)
  win            output 72   (9 x 8-bit, row-major: 0=TL..8=BR)
  window_valid   output 1    (1 when a full 3x3 window is available)

The window is built from a 3-wide column register that holds the last
three columns of each of the three rows (N-2, N-1, N).  When col_cnt>=2
and row_cnt>=2 the window is valid and the 9 values are exposed.
"""

class Window3x3:
    def __init__(self):
        # 3 rows x 3 columns of 8-bit pixels
        self.cols = [[0, 0, 0] for _ in range(3)]  # [row][col]
        self.win = [0] * 9
        self.window_valid = 0

    def reset(self):
        self.cols = [[0, 0, 0] for _ in range(3)]
        self.win = [0] * 9
        self.window_valid = 0

    def step(self, clk, rst_n, shift_en, pixel_in, lb0_data, lb1_data,
             col_cnt, row_cnt):
        if not rst_n:
            self.reset()
            return list(self.win), self.window_valid
        if clk and shift_en:
            # shift the 3-wide column registers left, push new column
            for r in range(3):
                self.cols[r] = self.cols[r][1:] + [0]
            self.cols[0][2] = int(lb0_data) & 0xFF   # row N-2
            self.cols[1][2] = int(lb1_data) & 0xFF   # row N-1
            self.cols[2][2] = int(pixel_in) & 0xFF   # row N
            # window valid when we have >=3 columns and >=3 rows
            if col_cnt >= 2 and row_cnt >= 2:
                self.window_valid = 1
                self.win = [self.cols[r][c] for r in range(3) for c in range(3)]
            else:
                self.window_valid = 0
        return list(self.win), self.window_valid