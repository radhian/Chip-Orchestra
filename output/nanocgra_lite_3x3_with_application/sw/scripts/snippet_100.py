# Let me finalize the architecture and verify the timing with a simulation trace.
#
# ARCHITECTURE:
# 1. line_buffer: 32-byte reg array, write at address, combinational read at address
#    - Actually, let me keep the shift register approach but fix the window assembly.
#    - The shift register approach works if we chain 2 line buffers AND use a cur_row shift register.
#    - The key: we need 3 rows of 3 columns. 
#    - With chained shift registers: lb0 (oldest row) -> lb1 (middle row) -> cur_row (newest row)
#    - pixel_in goes into cur_row, cur_row overflow goes into lb1, lb1 overflow goes into lb0
#    - After 32 pixels: cur_row = row 0 (partial), lb1 = garbage, lb0 = garbage
#    - After 64 pixels: cur_row = row 1 (partial), lb1 = row 0, lb0 = garbage  
#    - After 96 pixels (row 2, col c): cur_row = row 2 (partial), lb1 = row 1, lb0 = row 0
#    - For window at (row 0, col c-1) using rows 0, 1, 2:
#      lb0[31]=pixel(0,c), lb0[30]=pixel(0,c-1), lb0[29]=pixel(0,c-2)
#      lb1[31]=pixel(1,c), lb1[30]=pixel(1,c-1), lb1[29]=pixel(1,c-2)
#      cur_row[2]=pixel(2,c), cur_row[1]=pixel(2,c-1), cur_row[0]=pixel(2,c-2)
#    - This works! The window is centered at (row 1, col c-1) = output pixel (0, c-2)
#
# Wait, but the chaining means:
# - cur_row is a 3-element shift register: cur[2]<=pixel_in, cur[1]<=cur[2], cur[0]<=cur[1]
# - lb1 shifts in cur[0] (the pixel that falls off cur_row's left end)
# - lb0 shifts in lb1's mem[0] (the pixel that falls off lb1's left end)
#
# But cur_row is only 3 elements. After 3 pixels, cur[0] = pixel(r, c-2).
# After 32 pixels, cur[0] = pixel(r, c-2) where c=31, so pixel(r, 29).
# But we also need pixel(r, 30) and pixel(r, 31) which are in cur[1] and cur[2].
# That works for the current row.
#
# For lb1: it shifts in cur[0] on every pixel. After 32 pixels of row 0,
# lb1 = row 0 (all 32 pixels). After 32 more pixels of row 1, lb1 = row 1.
# The pixel that falls off lb1's left end goes into lb0.
# After 64 pixels, lb0 = row 0. After 96 pixels, lb0 = row 1, lb1 = row 2.
# Wait, that's wrong. Let me retrace:
#
# cur_row is 3-deep. It overflows after 3 pixels. But we shift on EVERY pixel.
# After pixel 0: cur = [_, _, p0]. cur[0] is still garbage.
# After pixel 1: cur = [_, p0, p1]. cur[0] is still garbage.
# After pixel 2: cur = [p0, p1, p2]. cur[0] = p0.
# After pixel 3: cur = [p1, p2, p3]. cur[0] = p1 (p0 falls off, goes to lb1)
#
# So lb1 gets: p0 (at pixel 3), p1 (at pixel 4), ..., p31 (at pixel 34).
# But pixel 32 is the start of row 1! So lb1 gets row 0 pixels starting at cycle 3.
# After pixel 34 (row 1, col 2): lb1[31] = p31 = pixel(0, 31), lb1[0] = p0 = pixel(0, 0)
# Wait, lb1 shifts left: mem[0]<=mem[1], ..., mem[31]<=cur[0].
# After 32 shifts (pixels 3-34): lb1 contains pixel(0, 0..31) but shifted in starting at pixel 3.
# lb1[31] = last shifted in = pixel(0, 31) (shifted in at pixel 34)
# lb1[0] = first shifted in = pixel(0, 0) (shifted in at pixel 3, now at position 0 after 31 more shifts)
# Wait, after 32 shifts, the first value (pixel 0) has moved from mem[31] to mem[31-31]=mem[0].
# So lb1 = [pixel(0,0), pixel(0,1), ..., pixel(0,31)] = row 0. Correct!
#
# After pixel 64 (row 2, col 0): lb1 has been shifting in row 1 pixels since pixel 35.
# After 32 more shifts (pixels 35-66): lb1 = row 1.
# But at pixel 64, only 29 row-1 pixels have been shifted in (pixels 35-63 = 29 pixels).
# So lb1 is a mix of row 0 and row 1. 
#
# The problem: the 3-element cur_row introduces a 3-pixel delay before pixels reach lb1.
# So lb1 is always 3 pixels behind. This means the rows in lb1 are not aligned properly.
#
# This is getting too complicated. Let me use the simpler approach:
# - 2 line buffers as reg arrays with explicit write address
# - Combinational read
# - 3-element shift register for current row
# - No chaining; controller writes to the correct buffer based on row_cnt

# Let me just simulate the simple approach to verify:
import numpy as np

# Simulate the architecture
img = np.array([int(l.strip(),16) for l in open('rtl/sobel_input.mem') if l.strip()], 
               dtype=np.int32).reshape(32,32)

# 2 line buffers, 32 bytes each, reg arrays
lb = [np.zeros(32, dtype=np.int32) for _ in range(2)]
# 3-element shift register for current row
cur = np.zeros(3, dtype=np.int32)

results = []
pixel_count = 0

for r in range(32):
    for c in range(32):
        pixel = img[r, c]
        
        # Read from line buffers BEFORE writing
        # lb[r%2] currently holds row r-2 (if r >= 2)
        # lb[(r-1)%2] currently holds row r-1 (if r >= 1)
        lb_n2 = lb[r % 2]  # will be overwritten, currently holds row r-2
        lb_n1 = lb[(r-1) % 2]  # holds row r-1
        
        # Shift cur_row
        cur[0] = cur[1]
        cur[1] = cur[2]
        cur[2] = pixel
        
        # Write pixel to lb[r%2] at address c
        lb[r % 2][c] = pixel
        
        # Assemble window if valid (r >= 2, c >= 2)
        if r >= 2 and c >= 2:
            # Row r-2: lb_n2[c-2], lb_n2[c-1], lb_n2[c]
            # Row r-1: lb_n1[c-2], lb_n1[c-1], lb_n1[c]
            # Row r:   cur[0], cur[1], cur[2] = pixel(r,c-2), pixel(r,c-1), pixel(r,c)
            w0 = lb_n2[c-2]; w1 = lb_n2[c-1]; w2 = lb_n2[c]
            w3 = lb_n1[c-2]; w4 = lb_n1[c-1]; w5 = lb_n1[c]
            w6 = cur[0]; w7 = cur[1]; w8 = cur[2]
            
            gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
            gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
            mag = abs(gx) + abs(gy)
            results.append(min(mag, 255))

results = np.array(results, dtype=np.uint8).reshape(30, 30)

# Compare with golden
with open('rtl/sobel_golden.mem') as f:
    golden = np.array([int(l.strip(),16) for l in f if l.strip()], dtype=np.uint8).reshape(30,30)

print("Match:", np.array_equal(results, golden))
print("Max diff:", int(np.max(np.abs(results.astype(int) - golden.astype(int)))))
print("First row results:", results[0,:5])
print("First row golden:", golden[0,:5])