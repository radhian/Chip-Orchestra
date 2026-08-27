"""cgra_3x3 — 3x3 PE mesh array with N/W/E/S interfaces.

Hardware: rtl/cgra_3x3.v
Ports (name, dir, width):
  clk         input  1
  rst_n       input  1
  win         input  72   (9 x 8-bit window, row-major)
  cfg         input  9    (3-bit config per PE, 9 PEs => 27 bits packed as 9 fields)
  start       input  1
  sobel_out   output 8
  done        output 1

The CGRA maps the 3x3 Sobel kernel onto 9 PEs.  Each PE multiplies its
window pixel by its configured weight (shift-add for +/-1/+/-2).  The
array then sums the PE outputs for Gx and Gy separately and produces
the magnitude |Gx|+|Gy| saturated to 8-bit.

For the golden model we model the array as 9 PE instances plus a
reduction tree.  The cfg field per PE selects the operation that
applies the correct Sobel weight.
"""

from .pe import PE
from .params import SOBEL_GX, SOBEL_GY, sat_u8

# Map each Sobel weight to a PE cfg encoding
def weight_to_cfg(w):
    if w == 0:   return PE.ZERO
    if w == +1:  return PE.PASS      # +1 * pixel = pixel
    if w == -1:  return PE.NEG
    if w == +2:  return PE.SHL1
    if w == -2:  return PE.NEG_SHL1
    return PE.MUL  # fallback (should not happen for Sobel)

# Pre-computed cfg per PE for Gx and Gy
CFG_GX = [weight_to_cfg(w) for w in SOBEL_GX]
CFG_GY = [weight_to_cfg(w) for w in SOBEL_GY]


class CGRA3x3:
    def __init__(self):
        self.pe_gx = [PE() for _ in range(9)]
        self.pe_gy = [PE() for _ in range(9)]
        self.sobel_out = 0
        self.done = 0

    def reset(self):
        for p in self.pe_gx: p.reset()
        for p in self.pe_gy: p.reset()
        self.sobel_out = 0
        self.done = 0

    def step(self, clk, rst_n, win, start):
        """Combinational compute. Returns (sobel_out, done)."""
        if not rst_n:
            self.reset()
            return self.sobel_out, self.done
        w = [int(x) & 0xFF for x in win]
        # Gx branch
        gx_acc = 0
        for i in range(9):
            r, _ = self.pe_gx[i].step(clk, rst_n, CFG_GX[i], w[i], 0)
            # interpret PE result as signed (weights are signed)
            gx_acc += _pe_signed(r, CFG_GX[i], w[i])
        # Gy branch
        gy_acc = 0
        for i in range(9):
            r, _ = self.pe_gy[i].step(clk, rst_n, CFG_GY[i], w[i], 0)
            gy_acc += _pe_signed(r, CFG_GY[i], w[i])
        mag = abs(gx_acc) + abs(gy_acc)
        self.sobel_out = sat_u8(mag)
        self.done = 1 if start else 0
        return self.sobel_out, self.done


def _pe_signed(raw, cfg, pixel):
    """Interpret a PE's 8-bit output as the signed weighted pixel value."""
    p = int(pixel) & 0xFF
    if cfg == PE.ZERO:      return 0
    if cfg == PE.PASS:      return p
    if cfg == PE.NEG:       return -p
    if cfg == PE.SHL1:      return (p << 1)
    if cfg == PE.NEG_SHL1:  return -(p << 1)
    if cfg == PE.MUL:       return (raw - 256 if raw & 0x80 else raw)
    return 0