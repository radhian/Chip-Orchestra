# Wait, there's a timing issue. Let me re-examine.
#
# If pixel_in, pixel_shift, col_cnt, row_cnt are combinational:
# - On cycle N when rx_valid fires:
#   - pixel_shift = 1 (combinational)
#   - pixel_in = rx_byte (combinational)
#   - col_cnt = pixel_cnt % 32 (combinational)
#   - row_cnt = pixel_cnt / 32 (combinational)
#   - Line buffer writes pixel at col_cnt (on clock edge, end of cycle N)
#   - Window computes look-ahead win (combinational, available during cycle N)
#   - sobel_core computes core_out (combinational, available during cycle N)
#   - cgra_3x3 registers core_out -> sobel_out available at cycle N+1
#   - Controller checks window_valid (combinational) -> if valid, go to S_TX_RESULT
#   - pixel_cnt increments on clock edge (end of cycle N)
#
# - On cycle N+1:
#   - sobel_out is valid (registered from cgra)
#   - Controller is in S_TX_RESULT: latches sobel_out, starts TX
#   - But wait - the controller transitioned to S_TX_RESULT at the end of cycle N.
#     So at cycle N+1, it's in S_TX_RESULT and can capture sobel_out. Correct!
#
# But there's a subtlety: the controller transitions to S_TX_RESULT at the end of cycle N
# (on the clock edge). At cycle N+1, it's in S_TX_RESULT. sobel_out was registered at the
# end of cycle N (by cgra_3x3). So at cycle N+1, sobel_out holds the result from the window
# that was valid during cycle N. Correct!
#
# But what about start_cgra? The cgra_3x3 has: done <= start.
# If start_cgra is combinational (= rx_valid && window_valid), then at cycle N:
#   start = 1, so at cycle N+1: done = 1.
# The controller can use done as an alternative to the state transition.
#
# Actually, let me simplify: the controller doesn't need start_cgra at all.
# It just needs to know when sobel_out is valid. Since the controller knows when
# a valid window was shifted (it checked window_valid), and sobel_out is registered
# (1-cycle delay), the controller can capture sobel_out on the next cycle.
#
# Let me also think about whether the controller needs to be in S_RECV to accept pixels.
# If the controller is in S_WAIT_TX and rx_valid fires, it ignores the pixel.
# The testbench must not send pixels during this time.
#
# For the testbench, the simplest approach: send a pixel, wait for the result TX to complete,
# then send the next pixel. This is slow but correct.
# Total time: 1024 pixels * (RX time + TX time) = 1024 * (4340 + 4340) = ~8.9M cycles.
# At 50MHz, that's ~178ms. Acceptable for a testbench.
#
# But actually, for the first 66 pixels (no result), the controller stays in S_RECV.
# For the remaining 958 pixels, 900 produce results. So:
# - 66 pixels: just RX, no TX wait
# - 900 pixels: RX + TX wait
# - 58 pixels: just RX (the last 2 columns of each row from row 2 onward... wait, no)
#   Actually, every pixel from (2,2) to (31,31) produces a result. That's 30*30 = 900.
#   Pixels (0,0)-(1,31) = 64 pixels: no result
#   Pixels (2,0)-(2,1) = 2 pixels: no result
#   Total no-result pixels: 66
#   Pixels (2,2)-(31,31) = 900: result
#   Total: 66 + 900 = 966. But we have 1024 pixels!
#   Remaining: 1024 - 966 = 58 pixels. These are... wait.
#   Row 0: 32 pixels, no result (row < 2)
#   Row 1: 32 pixels, no result (row < 2)
#   Row 2: 32 pixels, cols 0-1 no result, cols 2-31 = 30 results
#   Row 3-31: 29 rows * 32 pixels = 928 pixels, cols 0-1 no result (2*29=58), cols 2-31 = 30*29 = 870 results
#   Total results: 30 + 870 = 900. Correct.
#   Total no-result: 64 + 2 + 58 = 124. 900 + 124 = 1024. Correct.
#
# So the controller needs to handle 1024 input pixels and produce 900 output bytes.
# For the 124 no-result pixels, it just shifts and continues.
# For the 900 result pixels, it shifts, captures the result, and TXs it.
#
# Now, the controller FSM:
# - S_IDLE: wait for rx_valid. On rx_valid, shift pixel, go to S_RECV.
#   (pixel_cnt was 0, now becomes 1)
# - S_RECV: on rx_valid, shift pixel. If window_valid, go to S_CAPTURE.
#   Else stay in S_RECV.
# - S_CAPTURE: capture sobel_out (registered, valid this cycle), go to S_TX_START.
# - S_TX_START: start TX (tx_start=1), go to S_WAIT_TX.
# - S_WAIT_TX: wait for tx_done. On tx_done, go to S_RECV.
#
# Wait, S_CAPTURE and S_TX_START can be combined:
# - S_TX_RESULT: capture sobel_out into result_reg, start TX, go to S_WAIT_TX.
# But sobel_out is already valid at this cycle (registered from the previous cycle).
# So we can capture it and start TX in the same cycle.
#
# Actually, let me reconsider. The transition from S_RECV to S_TX_RESULT happens on the
# clock edge at the end of cycle N. At cycle N+1, the controller is in S_TX_RESULT.
# sobel_out was registered at the end of cycle N. So at cycle N+1, sobel_out is valid.
# The controller captures it: result_reg <= sobel_out, tx_start <= 1, go to S_WAIT_TX.
# At cycle N+2, the controller is in S_WAIT_TX. TX is in progress.
#
# This works! Let me also handle the combinational signals:
# - pixel_in = rx_byte (combinational, always available)
# - pixel_shift = rx_valid && (state == S_IDLE || state == S_RECV) (combinational)
# - col_cnt = pixel_cnt[4:0] (combinational, lower 5 bits of pixel_cnt)
# - row_cnt = pixel_cnt[10:5] (combinational, upper bits of pixel_cnt)
#   Wait, pixel_cnt is 11 bits (0..1023). col = pixel_cnt % 32 = pixel_cnt[4:0].
#   row = pixel_cnt / 32 = pixel_cnt[10:5]. Correct!
#
# On rx_valid in S_RECV or S_IDLE:
#   pixel_cnt <= pixel_cnt + 1 (registered, updates at end of cycle)
#   If window_valid (combinational check using current col_cnt, row_cnt):
#     state <= S_TX_RESULT
#   Else:
#     state <= S_RECV (or stay in S_RECV)
#
# The window_valid check uses the CURRENT col_cnt and row_cnt (combinational from pixel_cnt).
# This is the column and row of the pixel being shifted IN (the current pixel).
# The window is valid when col >= 2 and row >= 2.
# This matches the simulation: the first valid window is at pixel (2,2) = pixel_cnt 66.

print("Controller timing verified:")
print("- Combinational: pixel_in, pixel_shift, col_cnt, row_cnt")
print("- Registered: pixel_cnt, state, result_reg, tx_start, tx_data, status")
print("- S_RECV -> S_TX_RESULT on rx_valid && window_valid")
print("- S_TX_RESULT: capture sobel_out, start TX -> S_WAIT_TX")
print("- S_WAIT_TX: wait tx_done -> S_RECV")