import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']

def win_at(r,c):
    return [px[r-1][c-1],px[r-1][c],px[r-1][c+1],px[r][c-1],px[r][c],px[r][c+1],px[r+1][c-1],px[r+1][c],px[r+1][c+1]]

# The chip output doesn't match any simple window shift. The values look like they
# might be computed on WRONG pixels entirely - maybe the line buffer / window is broken.
# Let me check: chip[0]=100=0x64. What if the window pixels are wrong?
# Let me brute force: what 3x3 window of the input gives 100?
# Actually, let me think about the architecture differently.
# The chip output pattern: 100, 132, 10, 132, 12, 134, 12, 134, 12, 136, 16, 136, 20...
# These alternate between small (10,12,12,12,16,20) and large (132,134,134,134,136,136)
# Golden: 68, 56, 58, 60, 62, 60, 62, 60, 60, 58, 60, 60, 60, 58, 58
# The alternation in chip suggests maybe even/odd columns are getting different (wrong) data

# Let me check if the chip is reading the line buffer at the wrong column.
# The line buffer is a shift register. After shifting in N pixels of a row,
# mem[0]=oldest=col0, mem[31]=newest=col31.
# But the tap uses col_cnt. The issue: col_cnt is set to (pixel_cnt+1)&0x1F AFTER increment.
# So when pixel_cnt goes 0->1, col_cnt=1. But the line buffer just shifted in pixel 0.
# The window uses lb_data at col_cnt, but the line buffer hasn't been updated yet at that point
# (it updates on the same clock edge).

# Actually the key issue: the window_3x3 look-ahead uses sr registers that are ONE SHIFT BEHIND.
# Let me trace through the golden model vs RTL carefully.

# Golden model (top.py sobel_stream):
# For each pixel at (row, col):
#   rn2 = lb_rn2[col] (before update)  -- row N-2 at this col
#   rn1 = lb_rn1[col] (before update)  -- row N-1 at this col
#   shift wcols left, push [rn2, rn1, px] as new column
#   update line buffers
#   if col>=2 and row>=2: emit sobel of the window

# RTL:
# On rx_valid (same cycle): pixel_shift=1, pixel_in=rx_byte, col_cnt=(pixel_cnt+1)%32, row_cnt=(pixel_cnt+1)/32
# Line buffer shifts on this clock edge (posedge): mem[i]<=mem[i+1], mem[31]<=pixel_in
#   So AFTER this edge, mem contains the new pixel at [31] and everything shifted left.
#   But the tap lb0_col = lb0_row[8*col_cnt +: 8] uses the CURRENT (pre-edge) row_out? 
#   No - row_out is combinational from mem, and mem updates on posedge.
#   At the posedge, mem gets new values. After posedge, row_out reflects new mem.
#   But col_cnt also updates at posedge. So in the cycle AFTER rx_valid:
#     col_cnt = new value, row_out = new line buffer content
#   The window_3x3: win is combinational from sr registers (which update on posedge too)
#     and lb0_data, lb1_data (combinational from line buffers).

# The timing is complex. Let me just check: is the col_cnt used for tapping correct?
# After receiving pixel at index k (0-based), pixel_cnt becomes k+1.
# col_cnt = (k+1) % 32, row_cnt = (k+1) / 32.
# The line buffer has shifted in pixels 0..k. So mem[31] = pixel[k], mem[30]=pixel[k-1], etc.
# mem[31-j] = pixel[k-j], mem[i] = pixel[k-(31-i)] = pixel[k-31+i]
# We want to tap column col_cnt = (k+1)%32. 
# But the line buffer is a SHIFT register, not random access by column!
# After shifting in k+1 pixels, mem[31] = most recent = pixel[k] = col (k%32) of current row
# (if still in row 0). mem[30] = pixel[k-1] = col (k-1)%32.
# So mem[31] corresponds to col (k%32), NOT col (k+1)%32 = col_cnt!
# The tap is at col_cnt = (k+1)%32, but the newest pixel in the buffer is at col (k%32).
# So the tap is OFF BY ONE - it's tapping the column that will be filled NEXT, not the current one.

# Wait, but the line buffer is 32 deep and we shift every pixel. After 32 pixels (one row),
# mem[0]=pixel[0]=col0, mem[1]=pixel[1]=col1, ..., mem[31]=pixel[31]=col31.
# So mem[col] = pixel at column col. The tap at col_cnt should give mem[col_cnt].
# But col_cnt = (k+1)%32 where k is the pixel just received.
# If k=31 (just received col 31 of row 0), col_cnt = 0 (next is col 0 of row 1).
# The line buffer now has mem[0..31] = row 0 cols 0..31. Tapping col_cnt=0 gives mem[0]=col0. Correct!
# If k=32 (just received col 0 of row 1), col_cnt = 1. 
# Line buffer shifted: mem[0]<=mem[1]=row0col1, ..., mem[30]<=mem[31]=row0col31, mem[31]<=pixel[32]=row1col0
# So now mem[0]=row0col1, mem[1]=row0col2, ..., mem[30]=row0col31, mem[31]=row1col0
# Tapping col_cnt=1 gives mem[1]=row0col2. But we want row1col1 (the column of the pixel just received is col 0, and col_cnt=1 is the NEXT column).
# Hmm, this is getting complicated. The line buffer is being used as a shift register but tapped as if random access.

# THE BUG: The line buffer shifts on EVERY pixel, so after the first row, the correspondence
# between mem[index] and column number breaks. mem[col] only equals row[col] when exactly 32 pixels 
# have been shifted (a full row). Once row 1 starts, the shift continues and mem[0] becomes row0col1, etc.

# The golden model uses COLUMN-ADDRESSED line buffers (lb_rn2[col] = value), NOT shift registers!
# The RTL uses shift registers but taps them by column index - this is fundamentally broken.

print("The RTL line buffer is a shift register but is tapped by column index.")
print("The golden model uses column-addressed (random access) line buffers.")
print("After the first row, the shift register no longer maps mem[col] to column col.")