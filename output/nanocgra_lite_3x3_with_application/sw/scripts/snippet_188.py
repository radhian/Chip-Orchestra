import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']
flat = [p for row in px for p in row]

# But wait - the golden model uses a COLUMN-ADDRESSED line buffer (lb_rn2[col] = value),
# while the RTL uses a SHIFT register. Even if we fix the lb1 input, the shift register
# approach with column tapping is fundamentally broken for multi-row operation.
# 
# The golden model's functional sobel_stream uses column-addressed line buffers:
#   lb_rn2 = [0]*IMG_W, lb_rn1 = [0]*IMG_W
#   lb_rn2[col] = lb_rn1[col] (row N-1 becomes N-2)
#   lb_rn1[col] = px (current pixel becomes N-1)
# These are RANDOM ACCESS by column, not shift registers.
#
# The RTL line_buffer is a shift register: shift left, push new at right.
# After shifting in a full row (32 pixels), mem[0..31] = cols 0..31 of that row. Good.
# But when the NEXT row starts, it continues shifting, so mem[0] = col1 of prev row, etc.
# The column addressing breaks.
#
# The fix: make the line buffer COLUMN-ADDRESSED (write at col, read at col), like the golden model.
# OR: use the shift register approach but with proper staggered line buffers and tap the RIGHT end.
#
# Actually, looking at the golden model's TopModel.step (cycle-accurate):
#   lb0_data = self.lb0.tap(self.ctrl.col_cnt) if row>=2 else 0
#   lb1_data = self.lb1.tap(self.ctrl.col_cnt) if row>=1 else 0
#   self.lb1.step(clk, rst_n, 1, self.lb0.row[-1])  -- lb1 gets lb0's OLDEST
#   self.lb0.step(clk, rst_n, 1, self.ctrl.pixel_in) -- lb0 gets new pixel
# The .tap(col) reads row[col], and .step shifts. So lb0 is a shift register holding the
# most recent 32 pixels. After a full row, lb0.row[0..31] = cols 0..31.
# When row 1 starts, lb0 shifts in row1 pixels. After col 0 of row 1: lb0.row = [row0col1..row0col31, row1col0].
# So lb0.tap(col_cnt) where col_cnt=0 gives row0col1, NOT row1col0.
# This seems wrong too... unless the window logic accounts for it.
#
# Wait, the golden functional model (sobel_stream) is DIFFERENT from the cycle-accurate TopModel.
# The functional model uses column-addressed buffers. The cycle-accurate model uses shift registers.
# The TB compares against the functional model's output (sobel_stream).
# The RTL should match the functional model.
#
# So the RTL needs to implement the SAME algorithm as sobel_stream:
# - Column-addressed line buffers (write at col, read at col)
# - lb_rn2[col] = lb_rn1[col], lb_rn1[col] = px
# - Window: 3-wide column registers, shift left, push [rn2, rn1, px]
#
# The simplest fix: rewrite the line buffer to be column-addressed (RAM-like),
# and fix the top-level wiring to match the golden functional model.

# Let me simulate the golden functional model's approach with the RTL's window logic
# to make sure I understand what the RTL should do.

def correct_sim(pixels):
    """Simulate the correct datapath (matching golden sobel_stream)."""
    lb_rn2 = [0]*32  # row N-2
    lb_rn1 = [0]*32  # row N-1
    wcols = [[0,0,0] for _ in range(3)]
    results = []
    for idx, px in enumerate(pixels):
        row = idx // 32
        col = idx % 32
        px = int(px) & 0xFF
        rn2 = lb_rn2[col] if row >= 2 else 0
        rn1 = lb_rn1[col] if row >= 1 else 0
        for r in range(3):
            wcols[r] = wcols[r][1:] + [0]
        wcols[0][2] = rn2
        wcols[1][2] = rn1
        wcols[2][2] = px
        if row >= 1:
            lb_rn2[col] = lb_rn1[col]
        lb_rn1[col] = px
        if col >= 2 and row >= 2:
            w = [wcols[r][c] for r in range(3) for c in range(3)]
            gx, gy, out = sobel_compute(w)
            results.append(out)
    return results

results = correct_sim(flat)
print("Correct sim first 20:", results[:20])
print("Golden first 20:      ", [68,56,58,60,62,60,62,60,60,58,60,60,60,58,58,60,60,58,62,62])
print("Match?", results[:20] == [68,56,58,60,62,60,62,60,60,58,60,60,60,58,58,60,60,58,62,62])