import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']
flat = [p for row in px for p in row]

# Simulate the golden controller + datapath EXACTLY as the golden model does it.
# The controller _accept_pixel sets:
#   pixel_in = byte
#   pixel_shift = 1
#   pixel_cnt += 1
#   col_cnt = pixel_cnt % 32  (AFTER increment)
#   row_cnt = pixel_cnt // 32 (AFTER increment)
# Then checks: if row_cnt >= 2 and col_cnt >= 2: capture sobel_out
#
# The sobel_out is computed from the window, which uses the CURRENT (pre-edge) line buffer
# and window register values. The line buffers and window update on pixel_shift (same cycle).
#
# In the golden TopModel.step:
#   lb0_data = lb0.tap(col_cnt) if row_cnt >= 2 else 0  -- uses CURRENT col_cnt (post-increment)
#   lb1_data = lb1.tap(col_cnt) if row_cnt >= 1 else 0
#   w, valid = win.step(clk, rst_n, pixel_shift, pixel_in, lb0_data, lb1_data, col_cnt, row_cnt)
#   sobel_out, cgra_done = cgra.step(clk, rst_n, w, valid)
#   if pixel_shift:
#     lb1.step(clk, rst_n, 1, lb0.row[-1])  -- lb1 gets lb0's oldest
#     lb0.step(clk, rst_n, 1, pixel_in)      -- lb0 gets new pixel
#
# But the FUNCTIONAL model (sobel_stream) is different - it uses column-addressed buffers.
# The TB compares against sobel_stream. So the RTL must match sobel_stream.
#
# Let me check: does the cycle-accurate TopModel produce the same output as sobel_stream?
# The TopModel uses shift-register line buffers with .tap(col_cnt).
# After accepting pixel at (row, col), col_cnt = col, row_cnt = row.
# lb0 has been shifting. After pixel_cnt pixels shifted in:
#   lb0.row = [pixel[pixel_cnt-32], ..., pixel[pixel_cnt-1]]  (if pixel_cnt >= 32)
#   lb0.tap(col_cnt) = lb0.row[col_cnt] = pixel[pixel_cnt-32+col_cnt]
#   = pixel[pixel_cnt - 32 + col] where col = pixel_cnt % 32
#   = pixel[pixel_cnt - 32 + (pixel_cnt % 32)]
#   If pixel_cnt = 32*row + col: = pixel[32*row + col - 32 + col] = pixel[32*(row-1) + 2*col]
#   That's NOT the right pixel for row N-1 at column col!
#
# So the cycle-accurate TopModel is ALSO broken (same shift-register issue).
# The functional sobel_stream is the golden truth, and it uses column-addressed buffers.
# The RTL must implement column-addressed line buffers.

# So my fix plan:
# 1. Rewrite line_buffer.v to be column-addressed (write at wr_col, read at rd_col)
# 2. Fix top-level wiring: lb_rn1 writes current pixel at col, lb_rn2 writes lb_rn1's old value at col
# 3. Fix window_3x3 to use the column-addressed approach matching sobel_stream
# 4. Fix controller timing to match

# Actually, the simplest approach: make the line buffer a simple RAM that writes at col_cnt
# and reads at col_cnt. The window assembler uses 3-wide column shift registers.
# The key insight from sobel_stream:
#   - rn2 = lb_rn2[col] (read BEFORE update)
#   - rn1 = lb_rn1[col] (read BEFORE update)
#   - shift wcols left, push [rn2, rn1, px]
#   - lb_rn2[col] = lb_rn1[col] (old value)
#   - lb_rn1[col] = px
#   - if col >= 2 and row >= 2: emit sobel(wcols)

# In hardware, this means:
# - On pixel_shift (same cycle as rx_valid):
#   - Read lb_rn2[col_cnt] and lb_rn1[col_cnt] (combinational, pre-edge values)
#   - Window: shift column regs left, push [rn2, rn1, pixel_in] (at posedge)
#   - Line buffers: lb_rn2[col_cnt] <= lb_rn1[col_cnt], lb_rn1[col_cnt] <= pixel_in (at posedge)
#   - sobel_out is combinational from the NEW window (post-shift)
#   - But the controller captures sobel_out at the SAME posedge...
#
# The timing issue: sobel_out is combinational from win, which uses sr registers (pre-edge).
# The controller captures sobel_out at posedge. So it captures the PRE-edge win value.
# But the golden model computes sobel from the POST-shift window.
#
# In the golden functional model, the window is computed and sobel applied in the same
# iteration (same "cycle"). The window regs are updated, then sobel is computed on the new window.
# In RTL, the window regs update at posedge, and sobel is combinational from the registers.
# So at the posedge, sobel uses the OLD register values. The NEW values appear after posedge.
# The controller would need to capture sobel_out ONE CYCLE LATER.
#
# But the golden controller captures sobel_out in the SAME cycle as _accept_pixel.
# In the golden model, _accept_pixel updates col_cnt/row_cnt, then checks if row>=2 && col>=2,
# and if so captures sobel_out. The sobel_out was computed from the window which was updated
# in the same step.
#
# In RTL, the window update (sr registers) happens at posedge. The combinational win
# uses pre-edge sr values. So the sobel_out at the posedge is from the OLD window.
# To match the golden model, we need the sobel_out to reflect the NEW window.
#
# Solution: make the window combinational (look-ahead), computing what the window WILL BE
# after the shift, using pre-edge sr values + new data. This is what the current window_3x3.v
# tries to do! But it uses the wrong lb_data.
#
# Let me re-examine: the current window_3x3.v computes:
#   win = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
# This is the look-ahead: after shift, sr0_0<=sr0_1, sr0_1<=sr0_2, sr0_2<=lb0_data.
# So the new window column is [sr0_1_old, sr0_2_old, lb0_data] = [old col c-2, old col c-1, new col c]
# Wait no. After shift: sr0 = [sr0_1_old, sr0_2_old, lb0_data_new].
# The window is [sr0[0], sr0[1], sr0[2], sr1[0], sr1[1], sr1[2], sr2[0], sr2[1], sr2[2]]
# = [sr0_1_old, sr0_2_old, lb0_data, sr1_1_old, sr1_2_old, lb1_data, sr2_1_old, sr2_2_old, pixel_in]
# This IS the look-ahead window. Good.
# But lb0_data and lb1_data need to be the CORRECT row N-2 and N-1 pixels at column col_cnt.
# With the broken line buffers (both identical shift registers), these are wrong.

# So the fix is:
# 1. Make line buffers column-addressed (RAM write at col, read at col)
# 2. Wire lb_rn1 to write pixel_in at col_cnt, lb_rn2 to write lb_rn1's old value at col_cnt
# 3. The window look-ahead uses lb_rn2_data and lb_rn1_data (read at col_cnt, pre-edge)
# 4. The controller captures sobel_out at the same posedge (using the look-ahead window)

# Let me verify this approach with a simulation.
def fixed_rtl_sim(pixels):
    """Simulate the FIXED RTL datapath."""
    # Column-addressed line buffers
    lb_rn2 = [0]*32  # row N-2
    lb_rn1 = [0]*32  # row N-1
    # Window shift registers (pre-edge)
    sr0 = [0,0,0]  # row N-2: [col c-2, col c-1, col c]
    sr1 = [0,0,0]  # row N-1
    sr2 = [0,0,0]  # row N
    results = []
    pixel_cnt = 0
    
    for k, px_in in enumerate(pixels):
        px_in = int(px_in) & 0xFF
        # Controller: _accept_pixel sets col_cnt = (pixel_cnt+1)%32, row_cnt = (pixel_cnt+1)//32
        # But the col_cnt used for the window/line buffer is the POST-increment value.
        # Wait - in the golden controller, _accept_pixel increments pixel_cnt FIRST, then
        # sets col_cnt = pixel_cnt % 32. So col_cnt is the NEW value.
        # The line buffer read/write uses this NEW col_cnt.
        new_pixel_cnt = pixel_cnt + 1
        col = new_pixel_cnt % 32
        row = new_pixel_cnt // 32
        
        # Read line buffers at col (PRE-edge values, before update)
        rn2 = lb_rn2[col] if row >= 2 else 0
        rn1 = lb_rn1[col] if row >= 1 else 0
        
        # Look-ahead window (what the window will be after this shift)
        win = [sr0[1], sr0[2], rn2,
               sr1[1], sr1[2], rn1,
               sr2[1], sr2[2], px_in]
        
        # Check if valid window (using NEW col/row)
        if col >= 2 and row >= 2:
            gx, gy, out = sobel_compute(win)
            results.append(out)
        
        # Update line buffers (at posedge): lb_rn2[col] <= lb_rn1[col], lb_rn1[col] <= px_in
        if row >= 1:
            lb_rn2[col] = lb_rn1[col]
        lb_rn1[col] = px_in
        
        # Update window shift registers (at posedge)
        sr0 = sr0[1:] + [rn2]
        sr1 = sr1[1:] + [rn1]
        sr2 = sr2[1:] + [px_in]
        
        pixel_cnt = new_pixel_cnt
    
    return results

results = fixed_rtl_sim(flat)
print("Fixed RTL sim first 20:", results[:20])
print("Golden first 20:        ", [68,56,58,60,62,60,62,60,60,58,60,60,60,58,58,60,60,58,62,62])
print("Match?", results == [68,56,58,60,62,60,62,60,60,58,60,60,60,58,58,60,60,58,62,62])
# Check all
with open('context/golden_ref.json') as f:
    gref = json.load(f)
print("Full match?", results == gref)