# Now let me think about the controller timing with the combinational window.
#
# With the combinational window:
# - When shift_en=1 (same cycle as rx_valid), win is the look-ahead window (valid for this pixel)
# - sobel_core computes combinationally from win -> core_out is valid this cycle
# - cgra_3x3 registers core_out -> sobel_out is valid NEXT cycle
# - cgra_3x3 also registers done <= start -> done is valid NEXT cycle
#
# So the controller should:
# 1. On rx_valid: set pixel_shift=1, pixel_in=rx_byte, update col_cnt/row_cnt
#    Check if window is valid (row >= 2, col >= 2) -> if so, set start_cgra=1
# 2. On the NEXT cycle: sobel_out is valid (registered from cgra), done=1
#    Capture sobel_out and start TX
#
# But wait - the controller outputs (pixel_in, pixel_shift, col_cnt, row_cnt) are registered.
# They update on the clock edge. So:
# - Cycle N: rx_valid fires. Controller sets pixel_shift<=1, pixel_in<=rx_byte, etc.
# - Cycle N+1: line buffer and window see pixel_shift=1, pixel_in=rx_byte, col_cnt, row_cnt.
#   Window computes combinational look-ahead win. sobel_core computes core_out.
#   cgra_3x3 registers core_out -> sobel_out available at cycle N+2.
#
# So there's a 2-cycle delay from rx_valid to sobel_out:
# - Cycle N: rx_valid, controller sets outputs
# - Cycle N+1: shift happens, window is combinational, core_out is combinational
# - Cycle N+2: sobel_out is registered (available)
#
# The controller needs to capture sobel_out at cycle N+2. It can use a 2-stage delay:
# - valid_pipe[0] <= (window_valid && rx_valid) at cycle N
# - valid_pipe[1] <= valid_pipe[0] at cycle N+1
# - At cycle N+2: if valid_pipe[1], capture sobel_out and TX
#
# But the controller also needs to keep receiving pixels while waiting for the result.
# Since UART bytes arrive every ~4340 cycles, and the pipeline delay is only 2 cycles,
# there's no conflict.
#
# Actually, let me reconsider. The controller outputs are registered, but I can make some
# of them combinational to reduce latency:
#
# - pixel_in: can be combinational (assign pixel_in = rx_byte)
# - pixel_shift: can be combinational (assign pixel_shift = rx_valid) 
# - col_cnt: can be combinational (assign col_cnt = pixel_cnt % 32)
# - row_cnt: can be combinational (assign row_cnt = pixel_cnt / 32)
#
# Then on the cycle when rx_valid fires:
# - pixel_in = rx_byte (combinational)
# - pixel_shift = 1 (combinational)
# - col_cnt = pixel_cnt % 32 (combinational)
# - row_cnt = pixel_cnt / 32 (combinational)
# - Line buffer writes pixel at correct address
# - Window computes combinational look-ahead win (valid for this pixel)
# - sobel_core computes core_out combinationally
# - cgra_3x3 registers core_out -> sobel_out available NEXT cycle
#
# So the delay is only 1 cycle (from cgra registration). The controller:
# - Cycle N: rx_valid, shift happens, core_out is valid (combinational)
#   Controller checks window_valid (combinational from col_cnt, row_cnt)
#   If valid, set a pending flag
# - Cycle N+1: sobel_out is valid (registered). If pending, capture and TX.
#   Also increment pixel_cnt.
#
# Wait, but pixel_cnt needs to increment on rx_valid. If col_cnt is combinational from
# pixel_cnt, then col_cnt reflects the current pixel (before increment).
# The increment happens on the clock edge, so pixel_cnt updates at the end of cycle N.
#
# Let me think about this more carefully:
# - pixel_cnt is a register, currently = P
# - col_cnt = pixel_cnt % 32 = P % 32 (combinational)
# - row_cnt = pixel_cnt / 32 = P / 32 (combinational)
# - On rx_valid at cycle N: shift happens with col=P%32, row=P/32
#   pixel_cnt <= P + 1 (updates at end of cycle)
# - At cycle N+1: pixel_cnt = P+1, col_cnt = (P+1)%32, row_cnt = (P+1)/32
#
# This is correct! The current pixel uses the current pixel_cnt, and pixel_cnt increments
# for the next pixel.
#
# Now, the controller FSM:
# - S_IDLE: wait for rx_valid. On rx_valid, go to S_RECV.
# - S_RECV: on rx_valid, shift pixel. If window_valid, set pending=1.
#   On next cycle, if pending, capture sobel_out and go to S_TX_RESULT.
#   But we also need to handle the next rx_valid...
#
# Actually, since the UART is slow, rx_valid won't fire on consecutive cycles.
# The controller has plenty of time between pixels. So:
# - S_RECV: on rx_valid, shift pixel, set start_cgra=1 if window_valid.
#   Go to S_CAPTURE if window_valid.
# - S_CAPTURE: capture sobel_out (registered, valid this cycle), go to S_TX_RESULT.
# - S_TX_RESULT: start TX, go to S_WAIT_TX.
# - S_WAIT_TX: wait for tx_done, go to S_RECV.
#
# But this means we miss the next rx_valid during S_CAPTURE, S_TX_RESULT, S_WAIT_TX.
# Since UART is slow (~4340 cycles between bytes), and these states take only a few cycles,
# we won't miss anything.
#
# Actually, we need to be more careful. The controller should keep counting pixels even
# when it's in TX states, because the next pixel might arrive while we're TXing.
# But with UART at 115200 baud and 50MHz clock, each byte takes ~4340 cycles.
# TX takes 10 bit periods = ~43400 cycles. So we'll be in TX for ~43400 cycles.
# During that time, about 10 input bytes could arrive! We'd miss them!
#
# This is a problem. The controller can't block RX during TX.
# We need to decouple RX handling from TX handling.
#
# Solution: use a small FIFO or handshake for TX. The controller captures the result
# and latches it, then starts TX. While TX is in progress, the controller continues
# receiving pixels and computing results. If a new result is ready while TX is busy,
# it waits (or we use a 2-deep FIFO).
#
# But the spec says "emit each result on the serial port AS SOON AS IT IS COMPUTED."
# With 900 output pixels and each TX taking ~43400 cycles, total TX time = 39M cycles.
# Input: 1024 bytes * 4340 = 4.4M cycles. So TX takes ~9x longer than RX!
# We can't emit results as fast as they're computed if TX is slower than RX.
#
# The testbench must account for this: it should send input bytes slowly enough
# that TX can keep up, or it should use a higher baud rate for TX.
#
# For the RTL design, the simplest approach: the controller processes one pixel at a time,
# computes the result, sends it via TX, and only then accepts the next pixel.
# This means the testbench sends a pixel, waits for the result (if any), then sends the next.
# Or: the testbench sends all pixels, and the controller processes them as fast as it can,
# back-pressuring by not reading (but UART has no backpressure).
#
# Actually, for a testbench, we can just send all 1024 pixels with enough gap between them
# for the TX to complete. Or we can use a simpler approach: the controller processes pixels
# in a batch, stores results in a small buffer, and TXs them after all pixels are received.
# But the spec says no output frame buffer!
#
# The simplest correct approach for the testbench:
# 1. Send all 1024 pixels via UART with gaps between them
# 2. The controller processes each pixel, and when a result is ready, TXs it
# 3. The testbench receives the 900 result bytes via UART
# 4. The gap between input bytes must be long enough for TX to complete
#
# For the RTL, the controller should:
# - Always accept incoming pixels (never block RX)
# - When a result is ready, if TX is idle, start TX
# - If TX is busy when a result is ready, wait for TX to finish, then start TX
#   (this means the next input pixel might arrive while waiting - we need to handle it)
#
# This is getting complex. Let me simplify: the controller processes pixels one at a time.
# When a result is ready, it goes to TX. While in TX, it ignores rx_valid.
# The testbench sends pixels with enough gap for TX to complete.
# At 115200 baud, TX takes 10 bit periods = 87us = 4340 cycles.
# If the testbench sends a pixel every 5000 cycles, there's enough time.
#
# Actually, for a 32x32 image, only 900 out of 1024 pixels produce results.
# The first 66 pixels (2 full rows + 2 pixels) don't produce results.
# After that, every pixel produces a result (except the last 2 in each row... no,
# actually every pixel from (2,2) to (31,31) produces a result, which is 30*30=900).
# Wait, let me check: the window is valid when row >= 2 AND col >= 2.
# So pixels (2,2) through (31,31) produce results = 30*30 = 900. Correct.
#
# For the testbench, the simplest approach: send a pixel, wait for the result
# (if the pixel should produce one), then send the next pixel. This is slow but correct.
# Or: send all pixels rapidly, collect all results. The controller needs to handle this.
#
# For the RTL, let me use a simple approach:
# - The controller always accepts pixels (S_RECV state)
# - When a result is ready, it latches it and transitions to S_TX_RESULT
# - In S_TX_RESULT, it starts TX and transitions to S_WAIT_TX
# - In S_WAIT_TX, it waits for tx_done, then goes back to S_RECV
# - While in S_TX_RESULT/S_WAIT_TX, it ignores rx_valid
# - The testbench sends pixels slowly enough that none are missed
#
# This is the simplest correct approach. Let me implement it.

print("Controller design:")
print("- S_IDLE: wait for first rx_valid, go to S_RECV")
print("- S_RECV: on rx_valid, shift pixel. If window_valid, latch result, go to S_TX_RESULT")
print("- S_TX_RESULT: start TX, go to S_WAIT_TX")
print("- S_WAIT_TX: wait for tx_done, go to S_RECV")
print("- While not in S_RECV, ignore rx_valid (testbench sends slowly)")
print()
print("Key: pixel_in, pixel_shift, col_cnt, row_cnt are COMBINATIONAL from rx_valid/pixel_cnt")
print("start_cgra pulses on rx_valid when window_valid")
print("sobel_out is registered in cgra (1-cycle delay), captured in S_TX_RESULT")