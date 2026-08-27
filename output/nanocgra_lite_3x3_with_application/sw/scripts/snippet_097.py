# Let me trace the exact timing more carefully to understand the data flow.
# 
# The architecture as designed:
# - uart_rx produces rx_byte + rx_valid pulse when a byte arrives
# - nano_controller feeds pixel_in + pixel_shift to line_buffer and window_3x3
# - line_buffer outputs row_out (combinational read of all 32 bytes)
# - window_3x3 takes lb0_data, lb1_data (taps from line buffers), pixel_in, col_cnt, row_cnt
# - cgra_3x3 takes win, computes sobel_out (registered, 1-cycle delay)
# - controller captures sobel_out and sends via uart_tx
#
# CRITICAL ISSUE: The controller goes to S_TX_RESULT for 1 cycle, then S_NEXT (waits tx_done).
# During this time, if rx_valid fires, the pixel is LOST because the controller isn't in S_RECV.
# 
# For a 32x32 image with 900 output pixels, each output takes ~10 UART bit periods to transmit.
# At 115200 baud, each byte takes ~87us = ~4340 clock cycles at 50MHz.
# Input bytes also arrive every ~4340 cycles.
# So there's plenty of time between input bytes - the TX will finish long before the next RX.
# The testbench likely sends bytes with gaps, so this should work.
#
# But the TIMING of sobel_out capture is the real issue. Let me trace:
#
# Cycle N: rx_valid fires for pixel at (row=2, col=2) - the first valid window position.
#   Controller: pixel_shift<=1, col_cnt<=2, row_cnt<=2
#   Controller checks: new row>=2 && new col>=2 -> YES
#   Controller: result_reg <= sobel_out, state <= S_TX_RESULT
#   
#   BUT: sobel_out at cycle N is the result from the window assembled at cycle N-1 (cgra is registered).
#   At cycle N-1, the window was for pixel (row=2, col=1) - which has col=1, so window_valid=0.
#   Actually, the window module assembles win using OLD col_cnt/row_cnt.
#
# Let me trace cycle by cycle for the first few valid windows:
#
# After reset: col_cnt=0, row_cnt=0, pixel_cnt=0
# 
# Cycle 0: rx_valid for pixel 0 (row0,col0). 
#   Controller: pixel_shift<=1, pixel_cnt<=1, col_cnt<=1, row_cnt<=0
#   Window: shift_en=1, sees col_cnt=0, row_cnt=0 -> window_valid=0
#   Window shifts: cols2[2]<=pixel_in(=pixel0), but win not updated (window_valid=0)
#   CGRA: win is still 0 from reset, sobel_out=0
#
# Cycle 1: rx_valid for pixel 1 (row0,col1).
#   Controller: pixel_shift<=1, pixel_cnt<=2, col_cnt<=2, row_cnt<=0
#   Window: shift_en=1, sees col_cnt=1, row_cnt=0 -> window_valid=0
#
# ...continue until row 2...
#
# The problem: when the controller checks "new row>=2 && new col>=2" and captures sobel_out,
# the sobel_out is from the PREVIOUS cycle's window. The previous cycle's window was assembled
# with the previous col_cnt/row_cnt. So there's a 2-cycle delay:
#   - Cycle N: pixel arrives, window shifts (using old col/row), win updated
#   - Cycle N+1: cgra computes from win (registered), sobel_out available
#   - But controller already captured sobel_out at cycle N!
#
# So the controller captures the WRONG sobel_out - it's from the window before the current one.
# This means the results are shifted by one position.
#
# Actually wait - let me re-read the window_3x3. win is output reg, updated on shift_en.
# And cgra_3x3.sobel_out is also output reg, updated every clock.
# So:
#   Cycle N: shift_en=1 -> win updates (registered, available cycle N+1)
#   Cycle N+1: cgra sees new win -> sobel_out updates (registered, available cycle N+2)
#   
# But the controller captures sobel_out at cycle N (same cycle as shift_en).
# So it captures sobel_out from win that was set at cycle N-1, which was from shift at cycle N-2.
# That's 2 cycles stale!
#
# This is a real bug. The controller needs to wait for the pipeline to settle before capturing.
# 
# The fix: the controller should capture sobel_out 2 cycles after shifting, not on the same cycle.
# Or: make the sobel computation combinational (sobel_core already is, but cgra_3x3 registers it).

# Let me check: does the top module even exist?
import os
print("Top module exists:", os.path.exists('rtl/nano_cgra_3x3_sobel_accelerator_v4.v'))