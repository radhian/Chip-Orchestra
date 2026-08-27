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

# My cycle-by-cycle sim is too complex and has bugs. Let me take a simpler approach.
# The key insight: pixel_shift, pixel_in, col_cnt, row_cnt are ALL registered.
# They update at the posedge when rx_valid=1, but the line buffer and window
# also update at the SAME posedge using the OLD values.
# 
# So the sequence for pixel k (0-indexed) is:
# Cycle T (rx_valid=1):
#   Pre-edge: col_cnt_r = col(k-1), pixel_in_r = pixel(k-1), pixel_shift_r = shift(k-1)
#     win = look-ahead using sr (from k-1's shift) + lb at col(k-1) + pixel(k-1)
#     sobel_out = f(win)
#     Controller: if cur_col(k) >= 2 and cur_row(k) >= 2: capture sobel_out
#   Posedge: col_cnt_r <= col(k), pixel_in_r <= pixel(k), pixel_shift_r <= 1
#            Line buffer: mem[col(k-1)] <= pixel(k-1)
#            Window: sr shifts in lb at col(k-1) and pixel(k-1)
#
# Cycle T+1 (no rx_valid, pixel_shift_r=1):
#   Pre-edge: col_cnt_r = col(k), pixel_in_r = pixel(k), pixel_shift_r = 1
#     win = look-ahead using sr (just shifted at T) + lb at col(k) + pixel(k)
#     sobel_out = f(win)  -- this is the CORRECT window for pixel k!
#   Posedge: pixel_shift_r <= 0
#            Line buffer: mem[col(k)] <= pixel(k)
#            Window: sr shifts in lb at col(k) and pixel(k)
#
# So at cycle T, the captured sobel_out uses the window from pixel k-1's shift.
# The window at cycle T has sr registers that were last updated at cycle T-1 (for pixel k-2).
# And lb data at col(k-1).
# 
# This is getting really confusing. Let me just make the controller outputs COMBINATIONAL
# instead of registered. That's the clean fix.

# The fix: make pixel_in, pixel_shift, col_cnt, row_cnt combinational outputs.
# When rx_valid and state is IDLE or RECV:
#   pixel_shift = 1
#   pixel_in = rx_byte
#   col_cnt = pixel_cnt[4:0]
#   row_cnt = pixel_cnt[10:5]
# Otherwise:
#   pixel_shift = 0
#   pixel_in = 0 (or don't care)
#   col_cnt/row_cnt = don't care (no shift)
#
# pixel_cnt, state, result_reg, out_cnt remain registered.

print("Fix: make pixel_in, pixel_shift, col_cnt, row_cnt combinational.")
print("This ensures the line buffer and window see the correct values on the SAME cycle as rx_valid.")