# Let me think about the controller timing carefully.
#
# The data flow:
# 1. uart_rx receives a byte, pulses rx_valid for 1 cycle with rx_byte
# 2. Controller sees rx_valid, sets pixel_in=rx_byte, pixel_shift=1, updates col_cnt/row_cnt
# 3. line_buffer writes pixel at address col_cnt (the NEW col_cnt value)
#    Wait - col_cnt is a registered output. It updates on the same clock edge as the write.
#    So the line buffer sees the OLD col_cnt, not the new one!
#
# This is a problem. The controller needs to provide the column address to the line buffer.
# But col_cnt is registered, so it's 1 cycle behind.
#
# Solution: the controller should compute the column address combinationally and pass it
# to the line buffer. Or: use a separate col_addr signal that's set 1 cycle ahead.
#
# Actually, let me reconsider the whole timing. The controller has:
# - pixel_cnt: counts total pixels received (0..1023)
# - col_cnt = pixel_cnt % 32
# - row_cnt = pixel_cnt / 32
#
# When rx_valid fires:
# - The current pixel is pixel #pixel_cnt (0-indexed)
# - Its column is pixel_cnt % 32
# - Its row is pixel_cnt / 32
# - After processing, pixel_cnt increments
#
# So the controller should:
# - Use pixel_cnt (the CURRENT value, before increment) to compute col/row
# - Set pixel_in = rx_byte, pixel_shift = 1
# - The line buffer writes at address col = pixel_cnt % 32
# - Then increment pixel_cnt
#
# But col_cnt and row_cnt are registered outputs. They need to be available
# on the SAME cycle as pixel_shift. So they should reflect the CURRENT pixel,
# not the next one.
#
# Let me redesign: col_cnt and row_cnt should be combinational outputs based on pixel_cnt.
# Or: update them BEFORE setting pixel_shift.
#
# Actually, the simplest approach: make col_cnt and row_cnt combinational from pixel_cnt.
# pixel_cnt is the register; col_cnt and row_cnt are derived.
#
# Wait, but the controller also needs to check if the window is valid (row >= 2, col >= 2).
# And it needs to capture the sobel result. Let me think about the full pipeline:
#
# Cycle N: rx_valid fires for pixel #P (row R, col C)
#   Controller: pixel_in <= rx_byte, pixel_shift <= 1
#   col_cnt (combinational) = P % 32 = C
#   row_cnt (combinational) = P / 32 = R
#   Line buffer: wr_en=1, wr_addr=C, pixel_in=rx_byte (but pixel_in is registered!)
#     Wait, pixel_in is also a registered output. So the line buffer sees the OLD pixel_in.
#
# This is the fundamental issue: ALL controller outputs are registered, so they're 1 cycle behind.
# The line buffer sees the OLD pixel_in and OLD col_cnt.
#
# Solution: make pixel_in and col_cnt/row_cnt available on the SAME cycle as pixel_shift.
# Since pixel_shift is also registered, they all update together on the clock edge.
# The line buffer sees them on the NEXT cycle (after the edge).
#
# So:
# Cycle N: rx_valid fires. Controller sets pixel_in<=rx_byte, pixel_shift<=1, col_cnt<=C, row_cnt<=R
# Cycle N+1: line buffer sees pixel_shift=1, pixel_in=rx_byte, wr_addr=C. Writes pixel.
#            window_3x3 sees shift_en=1, pixel_in=rx_byte, col_cnt=C, row_cnt=R.
#            It reads lb[R%2][C] (combinational) and lb[(R-1)%2][C].
#            Shifts column registers, assembles window.
#            window_valid = (C >= 2 && R >= 2)
#            win is registered, available at cycle N+2.
# Cycle N+2: cgra_3x3 sees win (registered from window_3x3).
#            sobel_core computes combinationally from win.
#            cgra_3x3 registers sobel_out, available at cycle N+3.
# Cycle N+3: sobel_out is valid. Controller can capture it.
#
# But the controller is in S_RECV at cycle N, and it needs to know that a valid window
# was produced. It can check: was the pixel at (R, C) with R >= 2 and C >= 2?
# If so, the result will be available 3 cycles later (N+3).
#
# This is getting complex. Let me simplify by making more things combinational.
#
# SIMPLER APPROACH:
# - Make pixel_in a combinational output: assign pixel_in = rx_byte (wire, not reg)
# - Make col_cnt, row_cnt combinational from pixel_cnt
# - pixel_shift is registered (1-cycle pulse)
# - The line buffer and window see the correct values on the cycle AFTER rx_valid
#
# Actually, the cleanest approach is to make the controller outputs COMBINATIONAL where possible:
# - pixel_in = rx_byte (combinational pass-through)
# - col_cnt = pixel_cnt % 32 (combinational)
# - row_cnt = pixel_cnt / 32 (combinational)  
# - pixel_shift = rx_valid (combinational pass-through)
#
# Then on the cycle when rx_valid fires:
# - pixel_in = rx_byte (correct)
# - col_cnt = current column (correct)
# - row_cnt = current row (correct)
# - pixel_shift = 1 (correct)
# - Line buffer writes pixel at correct address
# - Window shifts with correct data
# - pixel_cnt increments on the clock edge
#
# But then the window is registered (available next cycle), and cgra is registered (available 
# the cycle after that). So the result is available 2 cycles after rx_valid.
#
# The controller needs to:
# 1. On rx_valid: shift pixel, increment pixel_cnt
# 2. Check if this pixel creates a valid window (row >= 2, col >= 2) - combinational
# 3. If valid, the result will be available 2 cycles later
# 4. Capture the result and send it via UART TX
#
# For step 3-4, the controller needs a pipeline delay. It can use a shift register:
# - valid_delay[0] <= (row >= 2 && col >= 2) on rx_valid
# - valid_delay[1] <= valid_delay[0]
# - When valid_delay[1] is set, sobel_out is valid -> capture and TX
#
# But the controller also needs to handle the case where it's busy TXing when the next
# result arrives. Since UART TX takes many cycles, and results arrive every ~4340 cycles,
# there's plenty of time.
#
# Actually, let me make it even simpler. Since the sobel_core is combinational and
# cgra_3x3 registers its output, the result is available 1 cycle after the window is valid.
# The window is registered, so it's valid 1 cycle after the shift.
# Total: 2 cycles from shift to sobel_out.
#
# But if I make the window combinational too (output the shift register values combinationally),
# then sobel_out is available 1 cycle after the shift (due to cgra registration).
# Or if cgra is also combinational, sobel_out is available on the same cycle as the shift.
#
# Let me make the window output combinational (not registered):
# The window module shifts its column registers on shift_en, but outputs win combinationally
# from the NEW values (using blocking assignments in a combinational block, or by computing
# the next values and outputting them).
#
# Actually, the simplest correct approach:
# - window_3x3: shift registers update on clock edge, win is COMBINATIONAL from the shift registers
#   (win reflects the CURRENT register values, which are from the PREVIOUS shift)
# - sobel_core: combinational
# - cgra_3x3: combinational output (don't register)
# - controller: on rx_valid, shift pixel. On the NEXT cycle, if the previous shift created
#   a valid window, capture sobel_out and TX.
#
# Wait, this still has the 1-cycle delay. Let me think differently.
#
# THE CLEANEST APPROACH: make everything combinational except the line buffer writes and
# column register shifts. The controller captures the result on the same cycle as the shift.
#
# If window_3x3 outputs win combinationally from the NEW shift values (not the registered ones),
# and sobel_core is combinational, then sobel_out is available on the same cycle as shift_en.
# The controller can capture it immediately.
#
# To do this, window_3x3 needs to compute the next window value combinationally and output it.
# This is like a "look-ahead" approach:
# - On shift_en, the new column values are: sr[0]<=sr[1], sr[1]<=sr[2], sr[2]<=new_data
# - The new window is: {sr[1]_old, sr[2]_old, new_data, ...}
# - This can be computed combinationally from the current register values + new inputs
#
# So win should be a combinational output that shows what the window WILL BE after the shift.
# Then sobel_core computes from this combinational win, and the result is available immediately.
#
# Let me redesign window_3x3 to output win combinationally (the next-state window).

print("Plan: window_3x3 outputs win combinationally (next-state after shift)")
print("sobel_core is combinational -> sobel_out available same cycle as shift_en")
print("Controller captures sobel_out on the same cycle as rx_valid/shift_en")