import numpy as np

img = np.array([int(l.strip(),16) for l in open('rtl/sobel_input.mem') if l.strip()], 
               dtype=np.int32).reshape(32,32)

# The issue: when we read lb[r%2] BEFORE writing, lb[r%2][c] still has the OLD value (row r-2, col c).
# But we're also writing to lb[r%2][c] = pixel(r,c). The read happens before the write (combinational).
# Let me check: at r=2, c=2, lb[0] should hold row 0.
# After r=0: lb[0] = row 0 (written at all 32 columns)
# After r=1: lb[1] = row 1 (written at all 32 columns), lb[0] still = row 0
# At r=2, c=0: we read lb[0] (which = row 0) and lb[1] (which = row 1). Correct!
#   We write pixel(2,0) to lb[0][0]. Now lb[0][0] = pixel(2,0), lb[0][1..31] = row 0.
# At r=2, c=1: we read lb[0] again. lb[0][0] = pixel(2,0) (just written!), lb[0][1..31] = row 0.
#   We need lb[0][1] = pixel(0,1) for the window. That's still correct (not overwritten yet).
#   We write pixel(2,1) to lb[0][1].
# At r=2, c=2: we read lb[0]. lb[0][0] = pixel(2,0), lb[0][1] = pixel(2,1), lb[0][2..31] = row 0.
#   For the window we need lb[0][0], lb[0][1], lb[0][2] = pixel(0,0), pixel(0,1), pixel(0,2).
#   But lb[0][0] = pixel(2,0) and lb[0][1] = pixel(2,1)! We've overwritten them!
#
# AH HA! The problem is that we're writing to lb[r%2] as we go, so by the time c=2,
# we've already overwritten columns 0 and 1 of the row r-2 data.
#
# The fix: we need to read the row r-2 data from a DIFFERENT buffer than the one we're writing to.
# But (r-2)%2 == r%2, so they're the same buffer!
#
# This is the fundamental issue with the circular buffer approach for K=3 with only 2 buffers.
# We need 3 buffers for 3 rows, but we only have 2 (K-1 = 2).
#
# The solution: the current row is NOT in a line buffer. It's in the cur_row shift register.
# So we need line buffers for rows N-2 and N-1 only. That's 2 buffers.
# The buffer assignment:
# - lb[0] and lb[1] alternate between holding row N-2 and row N-1
# - When row N arrives: lb[N%2] holds row N-2, lb[(N-1)%2] holds row N-1
# - We read from BOTH lb buffers (no writing to them during row N)
# - When row N completes, we need to update: the oldest row (N-2) is no longer needed,
#   and we need to store row N for use as N-1 in the next row.
# - So: lb[N%2] <- row N (the just-completed row), replacing row N-2
# - But we can't write a full row at once in a streaming design!
#
# The standard solution: write the current row to lb[N%2] AS IT ARRIVES, but read row N-2
# from the SAME buffer BEFORE the write. Since we read combinationally and write on the clock edge,
# we get the old value. But as we showed, by column c, columns 0..c-1 have been overwritten.
#
# The REAL solution: use a SHIFT REGISTER for the line buffer, not a random-access array.
# With a shift register, the old data shifts out naturally as new data shifts in.
# We tap the 3 rightmost positions for the window columns.
#
# Let me go back to the chained shift register approach, but fix the alignment.

# Chained shift registers: pixel_in -> cur_row (3-deep) -> lb1 (32-deep) -> lb0 (32-deep)
# All shift simultaneously on shift_en.
# cur_row: [c-2, c-1, c] for current row
# lb1: holds the row that was completed 1 row ago = row N-1
# lb0: holds the row that was completed 2 rows ago = row N-2
# 
# But the 3-deep cur_row means pixels are delayed by 3 before entering lb1.
# So lb1 is 3 pixels behind. After 32 pixels of row 0, only 29 have entered lb1.
# After 35 pixels (row 1, col 3): lb1 has all 32 pixels of row 0.
# 
# The 3-pixel delay means lb1 doesn't have a complete row until 3 pixels into the next row.
# This causes misalignment.
#
# Alternative: don't chain through cur_row. Instead:
# - Shift pixel_in directly into lb1 (32-deep shift register)
# - lb0 shifts in lb1's overflow (lb1[0] before it's lost)
# - cur_row is a SEPARATE 3-deep shift register that also gets pixel_in
# - All three shift on the same shift_en
#
# This way:
# - lb1 gets every pixel directly (no delay)
# - After 32 pixels: lb1 = row 0
# - After 64 pixels: lb1 = row 1, lb0 = row 0 (lb0 got lb1's overflow)
# - After 96 pixels (row 2, col c): lb1 = row 2 (partial), lb0 = row 1
#   But we need row 0 (N-2)! lb0 = row 1 (N-1), not row 0 (N-2).
#   Row 0 was in lb0 before row 1 started, but it got shifted out into... nowhere.
#   lb0's overflow is lost.
#
# So we need: pixel -> lb1 -> lb0, and lb0's overflow is lost.
# After row 0: lb1 = row 0, lb0 = garbage
# After row 1: lb1 = row 1, lb0 = row 0
# After row 2, col c: lb1 = partial row 2, lb0 = row 1
#   We need rows 0, 1, 2. lb0 = row 1, lb1 = partial row 2. Row 0 is LOST.
#
# We need 3 rows but only have 2 line buffers. The current row (row 2) is in lb1 (partially)
# and in cur_row. But we need row 0 which is gone.
#
# THE FUNDAMENTAL ISSUE: with K-1 = 2 line buffers for a K=3 kernel, we can hold 2 rows.
# The current row (row N) is not in a line buffer - it's the one being received.
# So the 2 line buffers hold rows N-2 and N-1. The current pixel + shift register gives row N.
#
# For this to work, the line buffers must NOT be shifted with the current row's pixels.
# They hold completed rows only. When a row completes, one line buffer is updated.
#
# But we can't update a full row at once in streaming! 
# UNLESS we use the circular buffer approach where we write the current row to one buffer
# while reading the previous rows from the other buffer.
#
# The circular buffer approach works if we have SEPARATE read and write ports, or if we
# read the old value before writing. The issue was that by column c, columns 0..c-1 are overwritten.
# But we need columns c-2, c-1, c from row N-2. Columns c-2 and c-1 have been overwritten!
#
# SOLUTION: use a SHIFT REGISTER for the line buffer, and tap the 3 rightmost positions.
# The shift register naturally shifts out old data as new data comes in.
# We DON'T need random access - we just need the 3 most recent columns.
#
# So: 2 line buffers as shift registers. The current row's pixels go into lb_write (selected by row%2).
# The other buffer (lb_read) holds the previous row.
# But we need 2 previous rows (N-2 and N-1), and we only have 1 other buffer.
#
# WAIT. I think I've been overcomplicating this. Let me re-read the design notes:
# "2 LINE BUFFERS of W bytes" for K=3. The current pixel is row N (not stored in a line buffer).
# So: lb0 = row N-2, lb1 = row N-1, current pixel = row N.
# The line buffers hold COMPLETED rows. They're updated when a row completes.
#
# For streaming, the update happens by writing the current row's pixels to the buffer
# that held row N-2 (which is no longer needed). This is the circular buffer approach.
# The buffer being written to (lb[r%2]) gets pixel(r, c) at position c.
# We read from it to get row N-2, but columns 0..c-1 have been overwritten.
# 
# THE KEY INSIGHT: we don't need columns 0..c-1 from row N-2! We need columns c-2, c-1, c.
# And column c hasn't been written yet (we're about to write it).
# But columns c-2 and c-1 HAVE been written (with row N data, not row N-2 data).
#
# So the circular buffer approach with random access DOESN'T WORK for K=3 with 2 buffers.
# We need 3 buffers, or we need a different approach.
#
# THE CORRECT APPROACH: use 2 line buffers as SHIFT REGISTERS, chained:
# pixel -> lb_write -> lb_read
# where lb_write is the current row being built, and lb_read is the previous completed row.
# The shift registers give us the 3 rightmost pixels (columns c-2, c-1, c).
# But we need 2 previous rows, and lb_read only gives us 1.
#
# So we need: cur_row (3-deep shift reg) + lb1 (32-deep shift reg) + lb0 (32-deep shift reg)
# where pixel goes into cur_row, cur_row overflow goes into lb1, lb1 overflow goes into lb0.
# After 32+3 = 35 pixels: lb1 = row 0, lb0 = garbage
# After 64+3 = 67 pixels: lb1 = row 1, lb0 = row 0
# After 96+3 = 99 pixels: lb1 = row 2, lb0 = row 1
#   But we need row 0! lb0 = row 1, not row 0.
#
# The 3-pixel delay from cur_row means everything is shifted by 3. So:
# After 99 pixels: cur_row = [pixel(3,2), pixel(3,1), pixel(3,0)] (row 3, cols 0-2)
#   lb1 = row 2, lb0 = row 1. We need rows 1, 2, 3 for the window at row 2.
#   cur_row gives row 3 (cols 0-2), lb1 gives row 2, lb0 gives row 1. 
#   That's rows 1, 2, 3 - correct for output row 1 (centered at row 2)!
#
# But the 3-pixel delay means the window is at column c-2 (not c). Let me check:
# At pixel 99 (row 3, col 3): cur_row = [p(3,1), p(3,2), p(3,3)]
#   lb1[31] = p(2,3), lb1[30] = p(2,2), lb1[29] = p(2,1)
#   lb0[31] = p(1,3), lb0[30] = p(1,2), lb0[29] = p(1,1)
#   Window: rows 1,2,3, cols 1,2,3. Centered at (2,2). Output pixel (1,1). Correct!
#
# But the first valid window should be at output (0,0), centered at (1,1), using rows 0,1,2.
# With the 3-pixel delay, the first valid window is at pixel 99 (row 3, col 3), 
# centered at (2,2), which is output (1,1). We've skipped output (0,0) and the rest of row 0!
#
# The 3-pixel delay from cur_row causes us to miss the first 3 output columns of each row.
# That's wrong.
#
# OK, I think the issue is that cur_row should NOT be in the chain. It should be parallel.
# Let me try: 
# - pixel goes into cur_row (3-deep) AND into lb1 (32-deep) simultaneously
# - lb1 overflow goes into lb0
# - All shift on the same shift_en
#
# After 32 pixels: cur_row = [p(0,29), p(0,30), p(0,31)], lb1 = row 0, lb0 = garbage
# After 64 pixels: cur_row = [p(1,29), p(1,30), p(1,31)], lb1 = row 1, lb0 = row 0
# After 96 pixels (row 2, col 31): cur_row = [p(2,29), p(2,30), p(2,31)], lb1 = row 2, lb0 = row 1
#   We need rows 0, 1, 2. lb0 = row 1, lb1 = row 2. Row 0 is LOST.
#
# Same problem. We need row N-2 but only have N-1 and N.
# The current pixel is row N, lb1 = row N, lb0 = row N-1. We're missing row N-2.
#
# THE REAL SOLUTION: the current pixel is NOT stored in a line buffer.
# Line buffers hold rows N-2 and N-1. The current row N is only in cur_row.
# When a row completes, the line buffers are rotated.
#
# For this, we need to write the current row to a line buffer as it arrives,
# but NOT read from that buffer for the N-2 row. Instead, read N-2 from the other buffer.
# But with 2 buffers and 3 rows (N-2, N-1, N), one buffer must hold 2 rows, which is impossible.
#
# THE ACTUAL STANDARD SOLUTION: 
# Use 2 line buffers as a circular buffer. Write the current row to lb[r%2].
# Read row N-2 from lb[r%2] (the same buffer, but the OLD values before they're overwritten).
# Read row N-1 from lb[(r-1)%2] (the other buffer).
# 
# The trick: read the OLD value from lb[r%2] BEFORE writing the new value.
# In hardware, this means: combinational read of lb[r%2][c] gives the old value (row N-2, col c).
# The write happens on the clock edge, updating lb[r%2][c] to pixel(r, c).
# 
# But we need columns c-2, c-1, c from row N-2. By the time we're at column c,
# columns 0..c-1 have already been overwritten with row N data!
# 
# UNLESS we use a SHIFT REGISTER for lb[r%2]. Then the old data (row N-2) shifts out
# as new data (row N) shifts in. We tap the 3 rightmost positions.
# But the 3 rightmost positions contain row N data (just shifted in), not row N-2!
# The row N-2 data is at the LEFT end, being shifted out.
#
# For a shift register: after shifting in c+1 pixels of row N,
# positions 31, 30, 29 = pixel(N, c), pixel(N, c-1), pixel(N, c-2) [row N, newest]
# positions 28, 27, ... = row N-2 data (older)
# position 0 = pixel(N-2, c+1) [about to fall off]
#
# We need row N-2 at columns c-2, c-1, c. These are at positions:
# pixel(N-2, c) is at position 31-(c+1) = 30-c (it was shifted in 32+c cycles ago... no)
# 
# Actually, let me think about it as: the shift register has 32 positions.
# Before row N starts, it holds row N-2: [p(N-2,0), p(N-2,1), ..., p(N-2,31)]
# After shifting in pixel(N, 0): [p(N-2,1), p(N-2,2), ..., p(N-2,31), p(N,0)]
# After shifting in pixel(N, 1): [p(N-2,2), p(N-2,3), ..., p(N-2,31), p(N,0), p(N,1)]
# After shifting in pixel(N, c): [p(N-2,c+1), ..., p(N-2,31), p(N,0), ..., p(N,c)]
#   Position 0 = p(N-2, c+1)
#   Position 31-c-1 = p(N-2, 31) = p(N-2, c + (31-c)) ... 
#   Let me just count: after c+1 shifts, the first c+1 positions are row N data (in reverse order),
#   and the remaining 32-(c+1) = 31-c positions are row N-2 data.
#   Position 31 = p(N, c) [newest]
#   Position 31-c = p(N, 0) [oldest of row N]
#   Position 31-c-1 = p(N-2, 31) [newest of row N-2 remaining]
#   Position 0 = p(N-2, c+1) [oldest of row N-2 remaining]
#
# For the window at column c, we need p(N-2, c-2), p(N-2, c-1), p(N-2, c).
# p(N-2, c) is at position... it was at position c before the shifts. After c+1 shifts, it's at
# position c - (c+1) = -1. It's FALLEN OFF! 
# p(N-2, c-1) was at position c-1. After c+1 shifts: position c-1-(c+1) = -2. Also fallen off!
# p(N-2, c-2) was at position c-2. After c+1 shifts: position c-2-(c+1) = -3. Also fallen off!
#
# So with a shift register, by the time we reach column c, the row N-2 data at columns c-2, c-1, c
# has already been shifted out! We can't use a simple shift register for the circular buffer.
#
# CONCLUSION: The circular buffer approach requires RANDOM ACCESS (read before write at the same address).
# And the issue is that columns c-2, c-1 of row N-2 have been overwritten by row N data.
#
# So we CANNOT use 2 line buffers with a circular buffer scheme for K=3.
# We need 3 line buffers (K, not K-1), or a different architecture.
#
# Wait, but the design notes say K-1 = 2 line buffers. Let me re-read...
# "A 3x3 kernel over 32-wide rows is 2 x 32 B = 512 bits + 9 x 8 = 72 bits."
# "You need K-1 line buffers, NOT K: the last row is the arriving pixel itself."
#
# So the design says 2 line buffers. The arriving pixel is the current row (row N).
# The 2 line buffers hold rows N-2 and N-1.
# The current row N is built from the arriving pixels.
#
# For this to work, the line buffers must hold COMPLETED rows, not be shifted with every pixel.
# The line buffers are updated only when a row completes.
# 
# But how do we update a line buffer with a completed row in a streaming design?
# Answer: we write each pixel to the line buffer as it arrives, using the column as the address.
# The line buffer is a RANDOM ACCESS memory, not a shift register.
# We read from it at the current column to get the row N-2 or N-1 pixel.
#
# The circular buffer issue: lb[r%2] is being written with row N data while we read row N-2 from it.
# Columns c-2, c-1 have been overwritten. 
#
# BUT WAIT: we don't read from lb[r%2] for row N-2! We read from lb[(r-2)%2] = lb[r%2].
# Hmm, (r-2)%2 = r%2. So yes, we read from the same buffer we're writing to.
#
# THE SOLUTION: use 3 line buffers (not 2), or use a different addressing scheme.
# Actually, let me reconsider. Maybe the design notes are wrong about K-1, or maybe
# the approach is different.
#
# Actually, I think the standard approach with K-1 line buffers works like this:
# - The line buffers are FIFO shift registers, not random access
# - Each line buffer is W pixels deep
# - Pixels are streamed through the line buffers in series:
#   pixel -> lb0 -> lb1 -> output
# - After W pixels: lb0 = row 0
# - After 2W pixels: lb0 = row 1, lb1 = row 0
# - After 3W pixels: lb0 = row 2, lb1 = row 1
#   Current pixel = row 2, col W-1 (last pixel of row 2)
#   lb0 = row 2 (just completed), lb1 = row 1
#   But we need row 0! It's been shifted out of lb1.
#
# Hmm, this gives us rows N and N-1, not N-2 and N-1.
# 
# THE ACTUAL STANDARD APPROACH (I finally remember):
# For a KxK kernel, you need K-1 line buffers. Each line buffer is W pixels deep.
# The line buffers are chained: pixel -> lb0 -> lb1 -> ... -> lb(K-2)
# The current pixel is the K-th row (row N).
# lb0 = row N-1, lb1 = row N-2, ..., lb(K-2) = row N-(K-1)
# For K=3: lb0 = row N-1, lb1 = row N-2. Current pixel = row N.
# 
# The line buffers are SHIFT REGISTERS of depth W. Every pixel is shifted into lb0.
# lb0's overflow goes into lb1. lb1's overflow is discarded.
# 
# After W pixels (row 0): lb0 = row 0, lb1 = garbage
# After 2W pixels (row 1): lb0 = row 1, lb1 = row 0
# After 2W + c pixels (row 2, col c): lb0 = partial row 2, lb1 = row 1
#   lb0[31] = p(2,c), lb0[30] = p(2,c-1), lb0[29] = p(2,c-2)  [row N = row 2]
#   lb1[31] = p(1,c), lb1[30] = p(1,c-1), lb1[29] = p(1,c-2)  [row N-1 = row 1]
#   Current pixel = p(2,c) [row N = row 2]
#   But we need row N-2 = row 0! lb1 = row 1, not row 0.
#
# So lb0 = row N (current), lb1 = row N-1. We're missing row N-2.
# The current pixel is row N, which is also in lb0. We don't need a separate cur_row.
# But we need row N-2, which requires a 3rd line buffer.
#
# I think the design notes are WRONG about K-1 line buffers for this streaming approach.
# With chained shift registers, you need K line buffers (including the current row's buffer).
# The "K-1" count assumes the current row is NOT in a line buffer, but then you need
# random access to get columns c-2, c-1 from the current row, which requires a separate register.
#
# Let me just use 2 line buffers as chained shift registers + cur_row shift register:
# pixel -> cur_row (3-deep) for current row columns
# pixel -> lb0 (32-deep) for row N-1
# lb0 overflow -> lb1 (32-deep) for row N-2
# All shift simultaneously.
#
# After 32 pixels: cur_row = [p(0,29), p(0,30), p(0,31)], lb0 = row 0, lb1 = garbage
# After 64 pixels: cur_row = [p(1,29), p(1,30), p(1,31)], lb0 = row 1, lb1 = row 0
# After 96 pixels (row 2, col 31): cur_row = [p(2,29), p(2,30), p(2,31)], lb0 = row 2, lb1 = row 1
#   We need rows 0, 1, 2. lb1 = row 1, lb0 = row 2, cur_row = row 2 (cols 29-31).
#   Row 0 is LOST.
#
# SAME PROBLEM. With 2 line buffers + cur_row, we have rows N, N-1, and the last 3 cols of N.
# We're missing row N-2.
#
# THE SOLUTION: 3 line buffers chained: pixel -> lb0 -> lb1 -> lb2
# lb0 = row N, lb1 = row N-1, lb2 = row N-2
# Plus we tap the 3 rightmost positions of each for the window columns.
# No separate cur_row needed.
#
# But that's 3 line buffers = 3 * 32 = 96 bytes = 768 bits, which is still under budget.
# The design notes say 2 line buffers, but 3 is needed for correct operation.
# Actually, re-reading: "2 x 32 B = 512 bits + 9 x 8 = 72 bits" - that's 2 line buffers.
# But as we've shown, 2 isn't enough for a 3x3 kernel with streaming shift registers.
#
# Let me check: maybe the design uses the current pixel as one of the 3 row values,
# and only needs 2 line buffers for the other 2 rows. But the current pixel is just 1 value,
# and we need 3 values from the current row (cols c-2, c-1, c).
# So we need a 3-element shift register for the current row, PLUS 2 line buffers for N-1 and N-2.
# That's 2 * 32 + 3 = 67 bytes = 536 bits. Still under budget.
#
# The issue is: how do the 2 line buffers get filled? They need to hold rows N-1 and N-2.
# If we shift every pixel into lb0, and lb0 overflows into lb1:
# lb0 = row N (current), lb1 = row N-1. We're missing row N-2.
# We need lb0 = row N-1, lb1 = row N-2, and cur_row = row N.
# For this, the current row's pixels should NOT go into lb0.
# Instead, lb0 and lb1 should be updated only when a row completes.
#
# In a streaming design, this means: write the current row to a temporary location,
# and when the row completes, swap it into the line buffer chain.
# But that requires a full row buffer (32 bytes), which is another line buffer!
#
# OR: use the circular buffer approach with random access.
# Write pixel(r, c) to lb[r%2][c]. Read row N-2 from lb[r%2] (old values) and N-1 from lb[(r-1)%2].
# The problem: columns c-2, c-1 of lb[r%2] have been overwritten.
# 
# SOLUTION: read the old value BEFORE writing. In hardware, use a combinational read.
# lb[r%2][c] still holds p(N-2, c) when we read it at cycle c (before the write takes effect).
# But we also need p(N-2, c-1) and p(N-2, c-2), which were at columns c-1 and c-2.
# These were overwritten in previous cycles!
#
# UNLESS we save them. We can use a 3-element shift register for row N-2 as well:
# As we read p(N-2, c) from lb[r%2][c] (before writing), we shift it into a reg.
# Then we have p(N-2, c-2), p(N-2, c-1), p(N-2, c) in the shift register.
# Similarly for row N-1: read p(N-1, c) from lb[(r-1)%2][c] and shift into a reg.
# And for row N: the current pixel goes into a shift register.
#
# So the architecture is:
# - 2 line buffers (lb0, lb1) as reg arrays with combinational read at address c
# - Write pixel(r, c) to lb[r%2][c] on each shift_en
# - 3 shift registers (sr0, sr1, sr2) for the 3 rows, each 3 elements deep
# - On each shift_en:
#   - Read p(N-2, c) = lb[r%2][c] (combinational, before write)
#   - Read p(N-1, c) = lb[(r-1)%2][c] (combinational)
#   - p(N, c) = pixel_in
#   - Shift sr0: sr0[0]<=sr0[1], sr0[1]<=sr0[2], sr0[2]<=p(N-2,c)
#   - Shift sr1: sr1[0]<=sr1[1], sr1[1]<=sr1[2], sr1[2]<=p(N-1,c)
#   - Shift sr2: sr2[0]<=sr2[1], sr2[1]<=sr2[2], sr2[2]<=pixel_in
#   - Write lb[r%2][c] <= pixel_in
# - Window = {sr0[0], sr0[1], sr0[2], sr1[0], sr1[1], sr1[2], sr2[0], sr2[1], sr2[2]}
# - window_valid = (r >= 2) && (c >= 2)
#
# This uses 2 * 32 = 64 bytes for line buffers + 3 * 3 = 9 bytes for shift registers = 73 bytes.
# That's 584 bits, well under budget.
#
# Let me verify this with a simulation:

img = np.array([int(l.strip(),16) for l in open('rtl/sobel_input.mem') if l.strip()], 
               dtype=np.int32).reshape(32,32)

lb = [np.zeros(32, dtype=np.int32) for _ in range(2)]
sr0 = np.zeros(3, dtype=np.int32)  # row N-2
sr1 = np.zeros(3, dtype=np.int32)  # row N-1
sr2 = np.zeros(3, dtype=np.int32)  # row N

results = []

for r in range(32):
    for c in range(32):
        pixel = img[r, c]
        
        # Read BEFORE write (combinational read)
        p_n2 = lb[r % 2][c]  # row N-2, col c (old value before overwrite)
        p_n1 = lb[(r-1) % 2][c]  # row N-1, col c
        
        # Shift registers
        sr0 = np.roll(sr0, -1); sr0[2] = p_n2
        sr1 = np.roll(sr1, -1); sr1[2] = p_n1
        sr2 = np.roll(sr2, -1); sr2[2] = pixel
        
        # Write to line buffer
        lb[r % 2][c] = pixel
        
        # Assemble window if valid
        if r >= 2 and c >= 2:
            w0=sr0[0]; w1=sr0[1]; w2=sr0[2]
            w3=sr1[0]; w4=sr1[1]; w5=sr1[2]
            w6=sr2[0]; w7=sr2[1]; w8=sr2[2]
            
            gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
            gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
            mag = abs(gx) + abs(gy)
            results.append(min(mag, 255))

results = np.array(results, dtype=np.uint8).reshape(30, 30)

with open('rtl/sobel_golden.mem') as f:
    golden = np.array([int(l.strip(),16) for l in f if l.strip()], dtype=np.uint8).reshape(30,30)

print("Match:", np.array_equal(results, golden))
print("Max diff:", int(np.max(np.abs(results.astype(int) - golden.astype(int)))))
print("Num results:", len(results.ravel()))
print("First row results:", results[0,:5])
print("First row golden:", golden[0,:5])