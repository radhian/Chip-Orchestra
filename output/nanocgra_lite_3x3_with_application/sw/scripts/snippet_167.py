# The main TB needs to:
# 1. Send 1024 pixels via UART (each byte = 1 pixel)
# 2. Receive 900 Sobel result bytes via UART
# 3. Compare against golden_output.mem
# 
# The UART baud rate is 115200 at 50MHz = 434 cycles per bit.
# Each byte = 10 bits (start + 8 data + stop) = 4340 cycles.
# 1024 input bytes = 1024 * 4340 = 4,440,160 cycles for input.
# 900 output bytes = 900 * 4340 = 3,906,000 cycles for output.
# Total = ~8.3M cycles. At 50MHz that's 0.17 seconds real time.
# In simulation at 10ns per cycle, that's 83ms of sim time.
# 
# This is feasible but will take a while. The TB needs to:
# - Generate UART serial for each input pixel
# - Capture UART serial output for each result byte
# 
# The top module has only data_i (UART RX in) and data_o (UART TX out).
# The controller processes pixels as they arrive and sends results as they're computed.
# 
# The controller FSM:
# S_IDLE -> S_RECV (on first rx_valid)
# S_RECV -> S_TX_RESULT (when row>=2 & col>=2, capture sobel_out)
# S_TX_RESULT -> S_NEXT (assert tx_start)
# S_NEXT -> S_RECV (on tx_done, if not all done)
# 
# So the controller interleaves input and output: it receives a pixel,
# if a valid window exists it sends the result, then waits for tx_done
# before receiving the next pixel.
# 
# This means the TB can't just blast all 1024 pixels at once. It needs to
# synchronize with the TX output. The controller blocks on tx_done before
# accepting the next pixel.
# 
# The TB approach:
# 1. Generate a UART byte sender task that serializes a byte onto data_i
# 2. Generate a UART byte receiver that captures bytes from data_o
# 3. Send pixels one at a time, and when the controller sends a result,
#    capture it
# 
# But the timing is tricky: the controller accepts a pixel (rx_valid),
# and if a window is valid, it goes to S_TX_RESULT and sends the result.
# While in S_TX_RESULT/S_NEXT, it doesn't accept new pixels (rx_valid is ignored).
# So the TB needs to wait for tx_done before sending the next pixel.
# 
# Actually, the UART RX will still receive bytes even if the controller
# ignores rx_valid. The RX will produce rx_valid pulses, but the controller
# won't process them in S_TX_RESULT/S_NEXT. So the TB needs to be careful
# not to send pixels while the controller is busy transmitting.
# 
# The simplest approach: 
# - Send one pixel via UART
# - Wait for the controller to process it (rx_valid pulse)
# - If the controller sends a result (tx_start), wait for tx_done
# - Then send the next pixel
# 
# But this is very slow. Each pixel takes 4340 cycles to send, plus
# 4340 cycles for each result. Total = 1024*4340 + 900*4340 = 8.3M cycles.
# 
# Actually, the controller only sends results when row>=2 and col>=2.
# For the first 66 pixels (2 rows + 2 cols), no results are sent.
# After that, each pixel produces one result (except when the controller
# is in S_TX_RESULT/S_NEXT, where it skips accepting pixels).
# 
# Let me think about the exact flow:
# - Pixels 0..63 (rows 0-1, cols 0-31): no results, just shift into line buffers
# - Pixel 64 (row 2, col 0): no result (col < 2)
# - Pixel 65 (row 2, col 1): no result (col < 2)
# - Pixel 66 (row 2, col 2): FIRST result! Controller goes to S_TX_RESULT
#   - Sends result via UART TX (4340 cycles)
#   - Waits for tx_done
#   - Goes back to S_RECV
# - Pixel 67 (row 2, col 3): result, send, wait...
# 
# So after the first 66 pixels, each pixel produces a result and the
# controller blocks for ~4340 cycles per result.
# 
# The TB approach:
# 1. Send all 1024 pixels via UART, one at a time
# 2. After each pixel, check if the controller is sending a result
# 3. If so, capture the result byte from data_o
# 4. Continue
# 
# But the TB can't easily "check if the controller is sending" because
# the controller's state is internal. The TB can only observe data_o.
# 
# Better approach: 
# - Send a pixel via UART (drive data_i with the serial frame)
# - After the pixel is sent, wait for either:
#   a. The next rx_valid (if no result, the controller is ready for the next pixel)
#   b. tx_start/tx_done (if a result is being sent)
# 
# But the TB doesn't have access to rx_valid or tx_start (they're internal).
# The TB only has data_i and data_o.
# 
# The simplest reliable approach:
# - Send ALL 1024 pixels back-to-back via UART
# - Simultaneously, capture ALL bytes received on data_o
# - After all pixels are sent, wait for remaining TX to complete
# - Compare captured bytes against golden output
# 
# But the controller blocks on tx_done before accepting the next pixel.
# If we send pixels faster than the controller can process them, the
# UART RX will buffer them (it receives one byte at a time), but the
# controller will miss rx_valid pulses while in S_TX_RESULT/S_NEXT.
# 
# This means the controller will SKIP pixels, and the results will be wrong.
# 
# So the TB MUST synchronize: send a pixel, wait for the result (if any),
# then send the next pixel.
# 
# The approach:
# 1. For each of the 1024 pixels:
#    a. Send the pixel byte via UART on data_i
#    b. After the byte is sent, check if data_o starts a UART frame
#       (falling edge from idle high to 0 = start bit)
#    c. If so, capture the result byte from data_o
#    d. Wait for data_o to return to idle (stop bit)
#    e. Then proceed to the next pixel
# 
# But this requires precise timing. The UART TX takes 4340 cycles per frame.
# The TB needs to sample data_o at the right times.
# 
# Actually, a simpler approach: use a UART receiver in the TB to capture
# bytes from data_o. The TB UART receiver samples data_o at the baud rate
# and produces captured bytes.
# 
# Let me implement this with tasks:
# - send_byte(byte): serializes a byte onto data_i at the baud rate
# - recv_byte(): waits for a start bit on data_o, captures the byte
# 
# The flow:
# 1. Reset the DUT
# 2. For each pixel (0..1023):
#    a. send_byte(pixel[i])
#    b. If we expect a result (pixel index >= 66 and not in a gap),
#       recv_byte() and store it
# 3. After all pixels, collect remaining results
# 4. Compare against golden
# 
# But the controller might not send a result for every pixel after 66.
# It depends on the exact FSM timing. Let me trace through the FSM:
# 
# The controller accepts a pixel on rx_valid. If row>=2 and col>=2,
# it captures sobel_out and goes to S_TX_RESULT. In S_TX_RESULT, it
# asserts tx_start and goes to S_NEXT. In S_NEXT, it waits for tx_done.
# 
# So for each pixel that produces a result:
# - rx_valid -> S_TX_RESULT -> S_NEXT (tx_start) -> wait tx_done -> S_RECV
# 
# The controller is in S_RECV when it can accept the next pixel.
# If we send the next pixel while the controller is in S_TX_RESULT/S_NEXT,
# the UART RX will produce rx_valid, but the controller ignores it.
# 
# So the TB needs to wait for tx_done before sending the next pixel.
# But the TB can't observe tx_done directly. It CAN observe data_o:
# when the TX frame completes (stop bit), tx_done pulses.
# 
# The approach:
# 1. Send a pixel via UART
# 2. After sending, wait a bit for the controller to process
# 3. Check if data_o has a start bit (result being sent)
# 4. If so, receive the result byte
# 5. Wait for data_o to return to idle
# 6. Send the next pixel
# 
# The timing: after sending a pixel (4340 cycles), the controller
# processes it on the next rx_valid (which occurs at the end of the
# UART RX frame). Then if a result is produced, the controller goes
# to S_TX_RESULT and starts the TX. The TX start bit appears on data_o
# almost immediately (on the next baud tick).
# 
# So after sending a pixel, the TB should:
# - Wait for data_o to go low (start bit of result) or stay high (no result)
# - The wait should be at least one baud period (434 cycles) to allow
#   the controller to process and start TX
# 
# This is getting complex. Let me use a simpler approach:
# - Send a pixel, then wait for the result (if expected) by monitoring data_o
# - Use a timeout to handle pixels that don't produce results
# 
# Actually, the cleanest approach is to use the baud rate for both
# sending and receiving, and synchronize based on data_o transitions.

# Let me calculate the total simulation time needed.
# 1024 pixels * 10 bits * 434 cycles = 4,440,160 cycles for sending
# 900 results * 10 bits * 434 cycles = 3,906,000 cycles for receiving
# But they're interleaved, so total = 4,440,160 + 3,906,000 = 8,346,160 cycles
# At 10ns per cycle = 83.5ms sim time. This is fine.

print("Main TB approach: send pixels via UART, capture results via UART, compare against golden")
print(f"Total cycles: ~8.3M, sim time: ~83ms")