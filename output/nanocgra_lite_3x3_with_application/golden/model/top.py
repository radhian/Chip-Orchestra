"""top — toplevel golden model: nano_cgra_3x3_sobel_accelerator_v4.

Hardware: rtl/nano_cgra_3x3_sobel_accelerator_v4.v
Top ports (name, dir, width):
  clk     input  1
  rst_n   input  1
  data_i  input  1   (UART RX serial in)
  data_o  output 1   (UART TX serial out)

This model wires together all sub-modules and exposes a cycle-accurate
 behavioural model AND a fast functional model.

Functional API (what TB_GEN / tests use):
  sobel_stream(pixels) -> list of output bytes
    pixels: flat list of IMG_W*IMG_H bytes (row-major)
    returns: flat list of OUT_W*OUT_H bytes (row-major)

The functional model uses the same sobel_core computation as the
hardware datapath; it is the DEFINITION OF CORRECT for the RTL.
"""

from .params import IMG_W, IMG_H, OUT_W, OUT_H
from .sobel_core import sobel_compute
from .sram_32b import SRAM32B
from .line_buffer import LineBuffer
from .window_3x3 import Window3x3
from .cgra_3x3 import CGRA3x3
from .uart_rx import UartRx
from .uart_tx import UartTx
from .nano_controller import NanoController
from .mmio_bus import MMIOBus
from .reset_sync import ResetSync


def sobel_stream(pixels):
    """Functional streaming Sobel on a flat pixel list.

    Mirrors the hardware streaming datapath:
      - 2 column-addressed line buffers (row N-2, row N-1)
      - current pixel is row N
      - 3x3 window assembled when row>=2 and col>=2
      - result emitted immediately (no output frame buffer)

    The line buffers are addressed by column (write-at-col, read-at-col)
    rather than shift registers, so that tapping column *col* always
    returns the correct pixel for that column regardless of how many
    shifts have occurred in the current row.
    Returns a flat list of OUT_W*OUT_H bytes.
    """
    assert len(pixels) == IMG_W * IMG_H, \
        f"expected {IMG_W*IMG_H} pixels, got {len(pixels)}"
    # Column-addressed line buffers: lb[rn2][col] = row N-2, lb[rn1][col] = row N-1
    lb_rn2 = [0] * IMG_W   # row N-2
    lb_rn1 = [0] * IMG_W   # row N-1
    # 3-wide column registers for the window: [row][col0..col2]
    wcols = [[0, 0, 0] for _ in range(3)]
    results = []
    for idx, px in enumerate(pixels):
        row = idx // IMG_W
        col = idx % IMG_W
        px = int(px) & 0xFF
        # Read row N-2 and row N-1 at current column (before update)
        rn2 = lb_rn2[col] if row >= 2 else 0
        rn1 = lb_rn1[col] if row >= 1 else 0
        # Shift window column registers left, push new column on the right
        for r in range(3):
            wcols[r] = wcols[r][1:] + [0]
        wcols[0][2] = rn2   # row N-2
        wcols[1][2] = rn1   # row N-1
        wcols[2][2] = px    # row N
        # Update line buffers: row N-1 becomes row N-2, current px becomes row N-1
        if row >= 1:
            lb_rn2[col] = lb_rn1[col]
        lb_rn1[col] = px
        # Emit result when a full 3x3 window is available
        if col >= 2 and row >= 2:
            w = [wcols[r][c] for r in range(3) for c in range(3)]
            gx, gy, out = sobel_compute(w)
            results.append(out)
    assert len(results) == OUT_W * OUT_H, \
        f"expected {OUT_W*OUT_H} results, got {len(results)}"
    return results


def sobel_array(pixels_2d):
    """Sobel on a 2D array (list of rows). Returns 2D OUT_H x OUT_W array."""
    flat = [p for row in pixels_2d for p in row]
    out = sobel_stream(flat)
    return [out[r*OUT_W:(r+1)*OUT_W] for r in range(OUT_H)]


class TopModel:
    """Cycle-accurate toplevel wiring all sub-modules.

    This is used by the toplevel test to verify the streaming datapath
    end-to-end.  It models the UART + controller + line buffers + window
    + CGRA + SRAM + MMIO bus.
    """

    def __init__(self):
        self.reset_sync = ResetSync()
        self.uart_rx = UartRx()
        self.uart_tx = UartTx()
        self.lb0 = LineBuffer(IMG_W)
        self.lb1 = LineBuffer(IMG_W)
        self.win = Window3x3()
        self.cgra = CGRA3x3()
        self.sram = SRAM32B()
        self.bus = MMIOBus()
        self.ctrl = NanoController()
        self.data_o = 1  # idle high
        self._rst_n = 0

    def reset(self):
        self.reset_sync.reset()
        self.uart_rx.reset()
        self.uart_tx.reset()
        self.lb0.reset()
        self.lb1.reset()
        self.win.reset()
        self.cgra.reset()
        self.sram.reset()
        self.bus.reset()
        self.ctrl.reset()
        self.data_o = 1
        self._rst_n = 0

    def step(self, clk, rst_async_n, data_i):
        """Advance one clock. Returns data_o."""
        rst_n = self.reset_sync.step(clk, rst_async_n)
        self._rst_n = rst_n
        rx_byte, rx_valid = self.uart_rx.step(clk, rst_n, data_i)
        tx_out, tx_done = self.uart_tx.step(clk, rst_n,
                                            self.ctrl.tx_start, self.ctrl.tx_data)
        self.data_o = tx_out
        # streaming pixel path
        lb0_data = self.lb0.tap(self.ctrl.col_cnt) if self.ctrl.row_cnt >= 2 else 0
        lb1_data = self.lb1.tap(self.ctrl.col_cnt) if self.ctrl.row_cnt >= 1 else 0
        w, valid = self.win.step(clk, rst_n, self.ctrl.pixel_shift,
                                 self.ctrl.pixel_in, lb0_data, lb1_data,
                                 self.ctrl.col_cnt, self.ctrl.row_cnt)
        sobel_out, cgra_done = self.cgra.step(clk, rst_n, w, valid)
        # shift line buffers
        if self.ctrl.pixel_shift:
            self.lb1.step(clk, rst_n, 1, self.lb0.row[-1])
            self.lb0.step(clk, rst_n, 1, self.ctrl.pixel_in)
        # controller
        self.ctrl.step(clk, rst_n, rx_byte, rx_valid, tx_done, cgra_done, sobel_out)
        return self.data_o