# Let me think about the line buffer management more carefully.
# 
# We have 2 line buffers. The question is: when do we swap them?
# 
# In a standard 2-line-buffer design for 3x3 convolution:
# - lb_prev holds row N-2, lb_curr holds row N-1
# - As pixels of row N arrive, they're NOT stored in a line buffer (they're the "current" row)
# - When row N completes, lb_prev <- lb_curr, lb_curr <- row N (the just-completed row)
# 
# But with shift-register line buffers, the approach is different:
# - Every pixel is shifted into BOTH the current-row shift register AND a line buffer
# - Actually no. Let me think about this differently.
#
# The standard streaming approach with 2 line buffers:
# - There are 2 line buffers, each 32 bytes (shift register)
# - Every incoming pixel is shifted into the "newest" line buffer
# - The line buffers form a chain: pixel -> lb1 -> lb0
#   (lb1 gets the pixel, lb0 gets lb1's oldest output)
# 
# Wait, that's not how shift registers work. Let me think again.
#
# With shift-register line buffers:
# - lb0 and lb1 are each 32-byte shift registers
# - On each shift_en:
#   - lb1 shifts in pixel_in (lb1[31] <= pixel_in, lb1[30] <= lb1[31], etc.)
#   - lb0 shifts in lb1's output (the pixel that falls off lb1's left end)
# 
# But a shift register doesn't have a "left end output" in the way I'm thinking.
# The line_buffer module shifts left: mem[0]<=mem[1], ..., mem[31]<=pixel_in
# So mem[0] is overwritten (lost). We'd need to capture mem[0] before it's lost.
#
# Actually, the standard approach is simpler:
# - Chain: pixel_in -> lb1 -> lb0
# - lb1.shift_en and lb0.shift_en are both asserted together
# - lb1.pixel_in = pixel_in (current pixel)
# - lb0.pixel_in = lb1.mem[0] (the pixel that falls off lb1's left end)
# 
# But lb1.mem[0] is the oldest pixel in lb1, which is the pixel from 32 cycles ago.
# After 32 pixels of row N, lb1 holds row N, and lb0 holds row N-1.
# After 64 pixels, lb1 holds row N+1 (well, row 2), lb0 holds row N.
# 
# Wait, let me trace more carefully:
# - Pixels 0-31 (row 0): shifted into lb1. lb0 gets lb1's overflow (garbage initially).
# - Pixels 32-63 (row 1): shifted into lb1. lb0 gets lb1's overflow = row 0 pixels.
#   After pixel 63: lb1 = row 1, lb0 = row 0
# - Pixels 64-95 (row 2): shifted into lb1. lb0 gets lb1's overflow = row 1 pixels.
#   After pixel 95: lb1 = row 2, lb0 = row 1
#   But we need row 0 for the window! We've lost row 0.
#
# The issue: with only 2 line buffers chained this way, we always have the current row and
# the previous row, but not the row before that. For a 3x3 window we need rows N-2, N-1, N.
#
# So the chaining should be: pixel -> lb0 -> lb1, where lb0 is the "newest" and lb1 is "oldest":
# - lb0.pixel_in = pixel_in
# - lb1.pixel_in = lb0.mem[0] (oldest pixel falling off lb0)
# - After 32 pixels: lb0 = row 0, lb1 = garbage
# - After 64 pixels: lb0 = row 1, lb1 = row 0
# - After 96 pixels: lb0 = row 2, lb1 = row 1
#   Now for pixel at (row 2, col c): lb0 = row 2 (current), lb1 = row 1 (N-1)
#   But we need row 0 (N-2)! We only have 2 line buffers.
#
# Hmm, the issue is that the current pixel is row N, and we need rows N-2 and N-1.
# With 2 line buffers, we can hold rows N-2 and N-1, and the current pixel is row N.
# So the line buffers should NOT include the current row.
#
# The correct approach:
# - lb0 holds row N-2, lb1 holds row N-1
# - Current pixel is row N (not stored in a line buffer, just in the cur_row shift register)
# - When a full row is received, the line buffers shift: lb0 <- lb1, lb1 <- cur_row
# 
# But with shift registers, we can't "copy" one to another easily. 
# The standard approach is a RING of 2 line buffers with a row counter:
# - Use row_cnt to determine which line buffer gets the current pixel
# - lb[0] and lb[1] alternate: even rows go to lb[0], odd rows to lb[1]
# - For row N: lb[N%2] gets the pixels, lb[(N-1)%2] = row N-1, lb[(N-2)%2] = row N-2
#   Wait, that's 3 rows in 2 buffers - doesn't work.
#
# Actually, the standard approach for K-1 line buffers with K=3:
# - 2 line buffers, used as a circular buffer
# - row_cnt % 2 selects which buffer to write to
# - For row N: write to lb[N%2]
#   - lb[(N-1)%2] = row N-1 (the other buffer)
#   - But row N-2 was in lb[N%2] before we started writing! We're overwriting it!
#   - We need to READ row N-2 from lb[N%2] BEFORE writing to it.
#
# With shift registers, we read and write simultaneously:
# - When pixel (r, c) arrives:
#   - We read lb[r%2] to get pixel (r-2, c) [the value that's about to be overwritten]
#   - We write pixel (r, c) into lb[r%2]
#   - We read lb[(r-1)%2] to get pixel (r-1, c)
#   - The current pixel is (r, c)
#
# But with a shift register, "reading the value about to be overwritten" means reading mem[0]
# (the oldest, which falls off the left end). And we write pixel_in at mem[31].
# These happen on the same clock edge, so mem[0] still holds the old value when we read it
# (combinational read before the edge).
#
# So the architecture is:
# - 2 line buffers (lb0, lb1), each 32-byte shift register
# - row_cnt selects which buffer to write to: write_en = (row_cnt % 2 == buffer_id)
# - The OTHER buffer holds row N-1
# - The buffer being written to holds row N-2 (in its current contents, before the shift)
# - We read mem[0] from the write buffer to get row N-2, col c (the oldest pixel)
#   Wait, no. mem[0] is the oldest = col 0 of the current row being built.
#   Actually, after shifting in 32 pixels of row N, the buffer holds row N.
#   But we're reading from it WHILE writing. 
#
# Hmm, this is getting complicated. Let me think about it differently.
#
# Actually, the simplest correct approach with the line_buffer module as designed:
# The line_buffer is a 32-byte shift register. It shifts on every pixel.
# We need 2 line buffers that form a CHAIN:
#   pixel_in -> lb_new -> lb_old
# where lb_new gets pixel_in and lb_old gets lb_new's oldest pixel.
#
# After row 0 (pixels 0-31): lb_new = row 0, lb_old = garbage
# After row 1 (pixels 32-63): lb_new = row 1, lb_old = row 0
# After row 2 (pixels 64-95): lb_new = row 2, lb_old = row 1
#   For pixel (2, c): lb_new[31] = pixel(2,c), lb_old[31] = pixel(1,c)
#   But we need pixel(0,c) for row N-2! It's gone from lb_old (which now holds row 1).
#
# So chaining 2 line buffers gives us rows N and N-1, not N-2 and N-1.
# We need the current pixel to be row N (not stored), and 2 line buffers for N-2 and N-1.
#
# The correct approach: DON'T shift the current row into a line buffer.
# Instead, use a 3-element shift register for the current row, and 2 line buffers
# that are updated only when a row completes.
#
# But "updated only when a row completes" means we need to write 32 bytes at once,
# which doesn't work with streaming.
#
# OK, let me look at this from a different angle. The standard 2-line-buffer approach:
#
# We have 2 line buffers used as a circular buffer (ping-pong):
# - lb[0] and lb[1], each 32 bytes
# - For row r, we write pixels to lb[r%2]
# - We read from lb[(r-2)%2] for row N-2 and lb[(r-1)%2] for row N-1
# - But (r-2)%2 == r%2, so the buffer we're writing to IS the one that held row N-2!
# - We read the N-2 value BEFORE it gets overwritten.
#
# With a shift register, we can't do random access. But we CAN do it if we read
# the "tap" at the right position. 
#
# Actually, the line_buffer module outputs the FULL row (row_out, 256 bits).
# We can tap any column from it. So we don't need a shift register for reading -
# we just tap the right column.
#
# But the problem is: when we're writing row N to lb[r%2], we're shifting in pixels
# one at a time. After shifting in pixel (r, c), lb[r%2] contains:
#   mem[31] = pixel(r, c), mem[30] = pixel(r, c-1), ..., mem[0] = pixel(r, c-31+... )
#   Actually, mem[0] = pixel(r, c-31) if c >= 31, or garbage if c < 31.
#   More precisely, after shifting in c+1 pixels of row r:
#   mem[31] = pixel(r, c), mem[30] = pixel(r, c-1), ..., mem[31-c] = pixel(r, 0)
#   mem[30-c..0] = leftover from row r-2 (the previous contents)
#
# So lb[r%2] contains a MIX of row r (new pixels) and row r-2 (old pixels being shifted out).
# The old pixels (row r-2) are at positions mem[0..30-c], and they're being shifted out.
# After shifting in pixel (r, c), mem[0] = pixel(r-2, c+1) (the pixel that's about to fall off).
# Wait no - let me trace more carefully.
#
# Before row r starts, lb[r%2] contains row r-2 (32 pixels).
# When pixel (r, 0) arrives: shift left, mem[0]<=mem[1], ..., mem[31]<=pixel(r,0)
#   After shift: mem[0] = old mem[1] = pixel(r-2, 1), mem[1] = pixel(r-2, 2), ..., 
#   mem[30] = pixel(r-2, 31), mem[31] = pixel(r, 0)
# When pixel (r, 1) arrives: shift left again
#   After shift: mem[0] = pixel(r-2, 2), mem[1] = pixel(r-2, 3), ..., mem[29] = pixel(r-2, 31),
#   mem[30] = pixel(r, 0), mem[31] = pixel(r, 1)
#
# So after pixel (r, c) is shifted in:
#   mem[31] = pixel(r, c)     [newest]
#   mem[30] = pixel(r, c-1)
#   ...
#   mem[31-c] = pixel(r, 0)
#   mem[30-c] = pixel(r-2, 31)  [oldest of row r-2 remaining]
#   ...
#   mem[0] = pixel(r-2, c+1)    [about to fall off next shift]
#
# For the 3x3 window at column c (with c >= 2), we need:
#   Row r-2, columns c-2, c-1, c:
#   pixel(r-2, c) = mem[30-c] (if c < 31, otherwise it's already fallen off)
#   pixel(r-2, c-1) = mem[31-c]... wait, this doesn't work because mem[31-c] = pixel(r, 0) for c=31.
#
# Hmm, this is getting really messy. The mixed content of the buffer makes it hard to tap.
#
# Let me reconsider. The STANDARD approach for streaming 2D convolution with K-1 line buffers
# uses RANDOM ACCESS line buffers (or shift registers with tap points), not simple shift registers.
#
# Actually, the cleanest approach for this design:
# Use 2 line buffers as simple shift registers, chained:
#   pixel_in -> lb1 -> lb0
# lb1 gets pixel_in, lb0 gets lb1's overflow (mem[0] before it's lost).
# 
# After row 0: lb1 = row 0, lb0 = garbage
# After row 1: lb1 = row 1, lb0 = row 0
# After row 2, col c: lb1 = partial row 2 (cols 0..c), lb0 = row 1
#   lb1[31] = pixel(2, c), lb1[30] = pixel(2, c-1), lb1[29] = pixel(2, c-2)
#   lb0[31] = pixel(1, c), lb0[30] = pixel(1, c-1), lb0[29] = pixel(1, c-2)
#   
#   For the 3x3 window at (row 1, col c-1) centered... wait, we need rows 0, 1, 2.
#   Row 0 is in lb0? No, lb0 = row 1. Row 0 was in lb0 before row 1 pixels came in.
#   After row 1: lb0 = row 1 (row 0 was shifted out into... nowhere, it's lost).
#
# So chaining 2 line buffers gives us rows N and N-1, not N-1 and N-2.
# We need 3 rows but only have 2 line buffers + current pixel.
# The current pixel gives us 1 value from row N, but we need 3 (cols c-2, c-1, c).
# 
# So we need a 3-element shift register for the current row, PLUS 2 line buffers for N-1 and N-2.
# The 2 line buffers must hold rows N-1 and N-2, NOT the current row.
# 
# The way to do this: the line buffers are NOT shifted on every pixel.
# They're only updated when a row completes. But that requires a full row buffer...
#
# OR: use the circular buffer approach with random-access reads.
# The line_buffer module outputs the full row (row_out). We can tap any column.
# We write to the buffer selected by row_cnt%2, and read from both buffers.
# The buffer being written to (lb[row%2]) contains a mix of old (row N-2) and new (row N) pixels,
# but we can compute which positions hold which.
#
# Actually, I think the cleanest approach is:
# - Use 2 line buffers with EXPLICIT write enable and address, not shift registers
# - Write pixel (r, c) to lb[r%2][c]
# - Read lb[(r-2)%2][c] for row N-2 and lb[(r-1)%2][c] for row N-1
# - Since (r-2)%2 == r%2, we read from the same buffer we're writing to, but at the same address
#   (we read the old value before the write takes effect)
#
# This is a single-port SRAM approach. We need the read value from BEFORE the write.
# With the sram_32b module, data_out is registered (1 cycle delay). That complicates things.
#
# Let me just use a simple approach: 2 line buffers as reg arrays with combinational reads.
# Write on posedge clk, read combinationally (before the write).

print("Cleanest approach: 2 line buffers as reg arrays with combinational read")
print("lb[r%2] is written with pixel(r,c) at address c")
print("Read lb[(r-2)%2][c] and lb[(r-1)%2][c] combinationally")
print("Plus 3-element shift register for current row")
print("Window is combinational, sobel is combinational, controller registers result")