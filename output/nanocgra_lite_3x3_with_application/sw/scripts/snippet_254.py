# The golden streaming model uses line buffers that are COLUMN-ADDRESSED (write at col, read at col).
# But the RTL line_buffer.v is ALSO column-addressed (write at wr_col, read at rd_col).
# 
# The key difference: in the golden model, the line buffer update happens AFTER reading:
#   rn2 = lb_rn2[col] (read old value)
#   ... then lb_rn2[col] = lb_rn1[col]; lb_rn1[col] = px (update)
#
# In the RTL, the line buffer is read combinationally (rd_data = mem[rd_col]) and written on the clock edge.
# So the read happens BEFORE the write — same as golden. Good.
#
# BUT there's a critical issue with the line buffer chain in the RTL top:
#   u_lb_rn1: wr_col=col_cnt, pixel_in=pixel_in  (writes current pixel to rn1)
#   u_lb_rn2: wr_col=col_cnt, pixel_in=lb_rn1_rd (writes lb_rn1's OLD value to rn2)
#
# lb_rn1_rd = mem_rn1[col_cnt] (combinational read, OLD value before write)
# So rn2 gets the old rn1 value, and rn1 gets the new pixel. That's correct!
#
# Now the window. The golden model uses wcols (3-wide column shift registers).
# The RTL window_3x3 uses sr0_0, sr0_1, sr0_2 etc.
#
# Let me trace the RTL window logic carefully.
# The RTL win is COMBINATIONAL (look-ahead):
#   win = {sr0_1, sr0_2, lb0_data,   // row N-2: [col c-2, col c-1, col c]
#           sr1_1, sr1_2, lb1_data,   // row N-1
#           sr2_1, sr2_2, pixel_in}   // row N
#
# After shift: sr0_0<=sr0_1, sr0_1<=sr0_2, sr0_2<=lb0_data
# So the look-ahead window shows: {sr0_1_old, sr0_2_old, lb0_data}
#   = {col c-2, col c-1, col c} for row N-2
#
# The golden model:
#   wcols[r] = wcols[r][1:] + [0]  (shift left, push 0)
#   wcols[0][2] = rn2  (row N-2 at col c)
#   wcols[1][2] = rn1  (row N-1 at col c)
#   wcols[2][2] = px   (row N at col c)
#   win = [wcols[r][c] for r in range(3) for c in range(3)]
#   = [wcols[0][0], wcols[0][1], wcols[0][2], ...]
#   = [col c-2, col c-1, col c, ...]
#
# So both should produce the same window. The window logic looks correct.
#
# The issue must be in the TIMING — when the controller captures sobel_out.
# Let me look at the controller more carefully.

# The controller:
# S_RECV: if rx_valid:
#   pixel_cnt <= pixel_cnt + 1  (registered, takes effect next cycle)
#   if cur_row >= 2 && cur_col >= 2:
#     result_reg <= sobel_out   (captures combinational sobel_out)
#     state <= S_TX_RESULT
#
# cur_col = pixel_cnt[4:0] (BEFORE increment)
# cur_row = pixel_cnt[10:5] (BEFORE increment)
#
# So when rx_valid fires for pixel at index pixel_cnt:
#   col_cnt = pixel_cnt % 32 (combinational, current value)
#   row_cnt = pixel_cnt / 32
#   pixel_shift = 1 (combinational)
#   The window shifts on THIS clock edge (posedge)
#   The window combinational output (look-ahead) shows the window AFTER this shift
#   sobel_out is combinational from win
#   result_reg <= sobel_out captures the look-ahead window's sobel result
#
# This seems correct IF the look-ahead window matches the golden model's window.
#
# BUT WAIT: the golden model updates wcols on the SAME step (clk edge), and the
# window is read AFTER the update. In the RTL, the window is look-ahead (combinational
# showing post-shift values), and sobel_out is captured on the same clock edge.
#
# The question is: does the RTL's combinational win match the golden's post-shift win?
#
# RTL win (combinational, before clock edge):
#   {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
#
# After clock edge:
#   sr0_0 <= sr0_1, sr0_1 <= sr0_2, sr0_2 <= lb0_data
#   So new sr0 = [sr0_1_old, sr0_2_old, lb0_data_old]
#   = [col c-2, col c-1, col c]  ✓
#
# Golden wcols after step:
#   wcols[0] = [old_wcols[0][1], old_wcols[0][2], rn2]
#   = [col c-2, col c-1, col c]  ✓ (if old wcols[0][1] = col c-2, etc.)
#
# This looks consistent. So why the mismatch?
#
# Let me think about the line buffer read timing more carefully.
# In the RTL:
#   lb_rn1_rd = u_lb_rn1.rd_data = mem_rn1[col_cnt]  (combinational, OLD value)
#   lb_rn2_rd = u_lb_rn2.rd_data = mem_rn2[col_cnt]  (combinational, OLD value)
#
# On clock edge:
#   u_lb_rn1: mem_rn1[col_cnt] <= pixel_in  (writes new pixel)
#   u_lb_rn2: mem_rn2[col_cnt] <= lb_rn1_rd (writes old rn1 value)
#
# So lb0_data (rn2) = old mem_rn2[col] = row N-2 at col c  ✓
#    lb1_data (rn1) = old mem_rn1[col] = row N-1 at col c  ✓
#
# This all looks correct. Let me check if the issue is that the controller
# captures sobel_out on the WRONG cycle.

# Actually, let me reconsider. The controller captures result_reg <= sobel_out
# on the SAME posedge that the window shifts. At that posedge:
#   - window sr registers update (shift)
#   - result_reg <= sobel_out (combinational, based on PRE-shift win)
#
# WAIT! result_reg <= sobel_out uses the combinational sobel_out which is
# based on the PRE-shift win (the look-ahead win). But the look-ahead win
# IS the post-shift win. So result_reg captures the correct value.
#
# Hmm, but actually in Verilog, on a posedge:
#   - All RHS values are evaluated using CURRENT (pre-edge) values
#   - All LHS assignments take effect AFTER the edge
#
# So result_reg <= sobel_out captures sobel_out computed from the CURRENT
# (pre-edge) combinational win, which is the look-ahead (post-shift) window.
# This is correct.
#
# Let me look at this from a different angle. The even indices match but odd don't.
# This is a very specific pattern. Let me check if the chip is somehow
# capturing the sobel_out from the WRONG pixel (off by one).

# Let me compute: what would the sobel result be if we used the window
# from one column earlier or later?

import sys, json
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
px = grid['pixels']

# Replicate streaming to get windows at each result index
IMG_W = 32
lb_rn2 = [0] * IMG_W
lb_rn1 = [0] * IMG_W
wcols = [[0, 0, 0] for _ in range(3)]
windows = []
for idx, pxx in enumerate(pixels):
    row = idx // IMG_W
    col = idx % IMG_W
    pxx = int(pxx) & 0xFF
    rn2 = lb_rn2[col] if row >= 2 else 0
    rn1 = lb_rn1[col] if row >= 1 else 0
    for r in range(3):
        wcols[r] = wcols[r][1:] + [0]
    wcols[0][2] = rn2
    wcols[1][2] = rn1
    wcols[2][2] = pxx
    if row >= 1:
        lb_rn2[col] = lb_rn1[col]
    lb_rn1[col] = pxx
    if col >= 2 and row >= 2:
        w = [wcols[r][c] for r in range(3) for c in range(3)]
        windows.append(w)

# chip[1] = 0x9c = 156
# golden[1] = 0x38 = 56
# What window gives 156?
print("Looking for out=0x9c=156:")
for i, w in enumerate(windows):
    out = sobel_compute(w)[2]
    if out == 0x9c and i < 30:
        print(f"  result index {i}: win={w}")

# Also check: what if the chip computes on window at (row, col+1) instead of (row, col)?
# i.e., the window is shifted by one column
print("\nChecking if chip[odd] = golden[odd] computed at col+1:")
for i in range(1, 20, 2):
    # golden window at index i is at (row=2+i//30, col=2+i%30)
    # what if chip used window at col+1 = index i+1?
    if i+1 < len(windows):
        out_shifted = sobel_compute(windows[i+1])[2]
        print(f"  chip[{i}]={hex(0x9c if i==1 else 0)} golden[{i}]={hex(sobel_compute(windows[i])[2])} golden[{i+1}]={hex(out_shifted)}")