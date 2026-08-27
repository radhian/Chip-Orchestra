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

# The chip output is closer now but still wrong. The pattern:
# chip: 72, 158, 60, 161, 66, 161, 64, 161, 66, 158, 66, 161, 66, 158, 60, 159
# golden: 68, 56, 58, 60, 62, 60, 62, 60, 60, 58, 60, 60, 60, 58, 58, 60
# 
# The odd indices have high values (158, 161, 161, 161, 158, 161...) = 0x9e, 0xa1
# Even indices: 72, 60, 66, 64, 66, 66, 66, 60, 64 - closer to golden but not exact
# 
# 0xa1 = 161 = 0xa1. 0x9e = 158. These have bit 7 set.
# 72 = 0x48, golden 68 = 0x44. Close but off by 4.
# 60 = 0x3c, golden 58 = 0x3a. Off by 2.
# 66 = 0x42, golden 62 = 0x3e. Off by 4.
# 64 = 0x40, golden 62 = 0x3e. Off by 2.
#
# The even-index values are CLOSE to golden (off by 2-4), and odd-index values are way off.
# This suggests the window is ALMOST right but has a subtle timing issue.
# The alternating pattern (even OK, odd bad) suggests col_cnt is toggling in a way
# that affects even vs odd columns differently.
#
# The issue might be that col_cnt is a REGISTERED output. When the controller sets
# col_cnt <= cur_col at the posedge, the line buffer and window see the NEW col_cnt
# in the NEXT cycle, not the current one. But the line buffer write also happens at
# the same posedge. So there's a timing mismatch.
#
# Let me think about this more carefully:
# At posedge (rx_valid=1):
#   Controller: col_cnt <= cur_col (= pixel_cnt[4:0]), pixel_shift <= 1, pixel_in <= rx_byte
#   Line buffer: writes pixel_in at wr_col=col_cnt. But col_cnt is the OLD registered value!
#     Because col_cnt is being updated at THIS posedge, the line buffer sees the OLD col_cnt.
#   Window: shifts with lb_data read at col_cnt (OLD value).
#
# So the line buffer writes at the OLD col_cnt, not the NEW one!
# And the window reads at the OLD col_cnt.
# 
# The controller sets col_cnt <= cur_col where cur_col = pixel_cnt[4:0] (pre-increment).
# But pixel_cnt is also being updated at this posedge (pixel_cnt <= pixel_cnt + 1).
# So cur_col = pixel_cnt[4:0] uses the OLD pixel_cnt. That's correct - it's the current pixel's col.
# But col_cnt (the registered output) won't update to cur_col until AFTER this posedge.
# The line buffer and window use col_cnt (the registered output), which is the PREVIOUS cycle's value.
#
# So there's a one-cycle delay: col_cnt lags behind by one cycle.
# When pixel 0 arrives: controller sets col_cnt <= 0. Line buffer uses OLD col_cnt (0 from reset). OK.
# When pixel 1 arrives: controller sets col_cnt <= 1. Line buffer uses col_cnt=0 (from pixel 0). WRONG!
#
# The fix: col_cnt should be COMBINATIONAL, not registered. Or the line buffer should use cur_col directly.
# 
# Actually, looking at the golden controller: col_cnt is set in _accept_pixel which runs
# "combinationally" (in the same cycle). In the golden model, step() is called and all outputs
# are available immediately. In RTL, registered outputs lag by one cycle.
#
# The fix: make col_cnt, row_cnt, pixel_in, pixel_shift combinational outputs based on rx_valid
# and pixel_cnt. When rx_valid is high:
#   pixel_shift = 1
#   pixel_in = rx_byte
#   col_cnt = pixel_cnt[4:0]  (combinational)
#   row_cnt = pixel_cnt[10:5] (combinational)
# And pixel_cnt updates at the posedge.

print("The issue: col_cnt/row_cnt/pixel_in/pixel_shift are registered, causing a 1-cycle delay.")
print("They need to be combinational when rx_valid is high.")