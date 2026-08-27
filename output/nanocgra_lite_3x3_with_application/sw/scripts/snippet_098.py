# Let me think about the cleanest architecture that produces bit-exact results.
#
# The simplest correct approach:
# 1. window_3x3 assembles win combinationally from line buffer taps + current pixel
#    Actually no - the window needs column registers. Let me think again.
#
# The streaming architecture for 3x3 Sobel:
# - 2 line buffers (each 32 bytes, shift register)
# - Line buffer 0 holds row N-2, line buffer 1 holds row N-1
# - Current pixel is row N
# - For each new pixel at column c:
#   - lb0 outputs the pixel at column c from row N-2
#   - lb1 outputs the pixel at column c from row N-1  
#   - current pixel is row N, column c
#   - We need a 3-wide window: columns c-2, c-1, c for all 3 rows
#   - So we need column registers: 3 registers per row, shifting as pixels arrive
#
# The line_buffer as designed is a 32-byte shift register. When pixel_in arrives:
#   - mem[0]<=mem[1], mem[1]<=mem[2], ..., mem[31]<=pixel_in
#   - So mem[31] = newest, mem[0] = oldest
#   - After pixel at column c arrives, mem[31] = pixel_c, mem[30] = pixel_{c-1}, mem[29] = pixel_{c-2}
#
# So the line buffer naturally gives us the 3 most recent pixels at positions [31],[30],[29].
# We don't even need separate column registers in window_3x3!
# 
# The window can be assembled combinationally:
#   win[0] = lb0[29] (row N-2, col c-2)  -- top-left
#   win[1] = lb0[30] (row N-2, col c-1)  -- top-mid
#   win[2] = lb0[31] (row N-2, col c)    -- top-right
#   win[3] = lb1[29] (row N-1, col c-2)  -- mid-left
#   win[4] = lb1[30] (row N-1, col c-1)  -- center
#   win[5] = lb1[31] (row N-1, col c)    -- mid-right
#   win[6] = pixel_in (row N, col c-2)   -- wait, no. pixel_in is the CURRENT pixel (col c)
#
# Hmm, but the current pixel is only 1 value. We need 3 values for row N: col c-2, c-1, c.
# The current pixel is col c. We need col c-1 and c-2 from row N too.
# But row N is being built - we don't have a line buffer for it yet (it's the current row).
# 
# So we DO need column registers for the current row (row N), OR we can use a third line buffer
# that gets written as we go. But the spec says K-1=2 line buffers.
#
# The standard approach: use 2 line buffers for rows N-2 and N-1, and a 3-element shift register
# for the current row N. The 3-element shift register holds the last 3 pixels of the current row.
#
# So window_3x3 should have:
# - 3 registers for row N (shifting in pixel_in)
# - Read taps from lb0 and lb1 for rows N-2 and N-1
#
# But the line_buffer gives us the FULL row. We need the 3 rightmost pixels.
# If line_buffer outputs row_out (packed 32 bytes), we can tap:
#   row_out[29*8 +: 8] = col c-2, row_out[30*8 +: 8] = col c-1, row_out[31*8 +: 8] = col c
#
# Wait, but the line buffer shifts on shift_en. After the shift, mem[31]=newest.
# The row_out is combinational (assign from mem). So after the clock edge where pixel c is shifted in,
# row_out[31] = pixel c, row_out[30] = pixel c-1, row_out[29] = pixel c-2.
#
# So the window can be PURELY COMBINATIONAL from the line buffer outputs + current row shift register!
# No need for the cols0/cols1/cols2 registers in window_3x3 for rows N-2 and N-1.
# We only need a 3-element shift register for the current row (row N).
#
# Actually, we can even avoid the current-row shift register if we use a different approach:
# The line buffers shift on every pixel. After pixel (r,c) is shifted in:
#   lb0 holds row r-2 (if r>=2), lb1 holds row r-1 (if r>=1)
#   lb0[31] = pixel(r-2, c), lb0[30] = pixel(r-2, c-1), lb0[29] = pixel(r-2, c-2)
#   lb1[31] = pixel(r-1, c), lb1[30] = pixel(r-1, c-1), lb1[29] = pixel(r-1, c-2)
#   For row r: we need pixel(r,c), pixel(r,c-1), pixel(r,c-2)
#   pixel(r,c) = pixel_in (just arrived, but not yet in any line buffer)
#   pixel(r,c-1) = the previous pixel that was shifted in 1 cycle ago
#   pixel(r,c-2) = the pixel shifted in 2 cycles ago
#
# So we need a 2-deep shift register for the current row to get c-1 and c-2.
# Or: we can use the fact that lb1 will have pixel(r-1,c) etc., but that's the wrong row.
#
# Simplest: window_3x3 has a 3-element shift register for the current row.
# On shift_en: cur[0]<=cur[1], cur[1]<=cur[2], cur[2]<=pixel_in
# Then: win = {lb0[29], lb0[30], lb0[31], lb1[29], lb1[30], lb1[31], cur[0], cur[1], cur[2]}
# Wait, need to get the ordering right.
# 
# Actually, let me reconsider. The line_buffer shifts LEFT: mem[0]<=mem[1], ..., mem[31]<=pixel_in
# So mem[31] is newest (just shifted in), mem[30] is 1 older, mem[29] is 2 older.
# row_out packs: row_out[g*8 +: 8] = mem[g], so row_out[31*8 +: 8] = mem[31] = newest.
#
# For the current row, we need a shift register too. Let's call it cur_row:
# cur_row[2] <= pixel_in (newest, col c)
# cur_row[1] <= cur_row[2] (col c-1)  
# cur_row[0] <= cur_row[1] (col c-2)
#
# Window (row-major, 0=TL):
# win[0] = lb0 col c-2 = row_out[29*8 +: 8]  (but this is mem[29])
# win[1] = lb0 col c-1 = row_out[30*8 +: 8]  (mem[30])
# win[2] = lb0 col c   = row_out[31*8 +: 8]  (mem[31])
# win[3] = lb1 col c-2 = lb1_row_out[29*8 +: 8]
# win[4] = lb1 col c-1 = lb1_row_out[30*8 +: 8]
# win[5] = lb1 col c   = lb1_row_out[31*8 +: 8]
# win[6] = cur_row[0] (col c-2)
# win[7] = cur_row[1] (col c-1)
# win[8] = cur_row[2] (col c) = pixel_in (after shift)
#
# But wait - the line buffers and cur_row all shift on the SAME clock edge.
# After the edge: lb0[31] = pixel(r-2, c), cur_row[2] = pixel(r, c)
# And the window is combinational from these registered values.
# So the window is available 1 cycle after the shift, combinationally.
# Then sobel_core (combinational) computes the result in the same cycle.
# Then cgra_3x3 registers it (1 more cycle).
#
# OR: make the whole thing combinational. window_3x3 outputs win combinationally,
# sobel_core computes combinationally, and the controller registers the result.
# That's the simplest and most correct approach.
#
# Let me redesign:
# - window_3x3: has cur_row shift register (3 bytes), outputs win combinationally
#   from lb0/lb1 taps + cur_row. window_valid is combinational from col_cnt/row_cnt.
# - sobel_core: combinational (already is)
# - cgra_3x3: uses sobel_core combinationally, registers output
# - controller: captures sobel_out 1 cycle after shift (when it's valid)
#
# Actually, the cleanest approach for the controller:
# When rx_valid fires and a valid window exists, the controller:
# 1. Shifts the pixel into line buffers + window (pixel_shift=1)
# 2. On the NEXT cycle, the window is valid and sobel_out is available (if combinational)
# 3. Capture sobel_out and start TX
#
# But this requires the controller to wait 1 cycle. Let me think about whether we can
# make it work in a single cycle...
#
# If window_3x3 outputs win combinationally from the CURRENT state (before shift),
# and we use the line buffer outputs BEFORE the shift... no, that doesn't work because
# the line buffer hasn't been updated yet.
#
# The key insight: the line buffer and window shift registers update on the clock edge.
# The window is only valid AFTER the shift. So:
# - Cycle N: rx_valid, pixel_shift=1, shift happens at end of cycle
# - Cycle N+1: window is valid (combinational from registered line buffer + cur_row)
#              sobel_core computes combinationally -> sobel_out available
#              cgra_3x3 registers it -> available cycle N+2
#              OR if cgra is combinational, available cycle N+1
#
# For the controller to work simply, let's make cgra_3x3 combinational (just wrap sobel_core).
# Then:
# - Cycle N: rx_valid, shift, controller notes "window will be valid next cycle"
# - Cycle N+1: sobel_out is valid, controller captures it and starts TX
#
# This requires a 1-cycle delay state in the controller. Let me redesign the controller.

print("Redesign plan:")
print("1. window_3x3: combinational win from lb taps + cur_row shift register")
print("2. cgra_3x3: combinational sobel_out (wrap sobel_core), registered done")
print("3. nano_controller: 1-cycle pipeline delay between shift and capture")
print("4. Top module: wire everything together")