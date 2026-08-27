import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]
IMG_W = 32
def get_pixel(r, c):
    return pixels[r*IMG_W + c]

def sobel_compute(win):
    w = [int(x) & 0xFF for x in win]
    gx = (-w[0] + w[2] - 2*w[3] + 2*w[5] - w[6] + w[8])
    gy = (-w[0] - 2*w[1] - w[2] + w[6] + 2*w[7] + w[8])
    mag = abs(gx) + abs(gy)
    out = max(0, min(255, mag))
    return gx, gy, out

# chip out[1] = 0x9c = 156. No clean 3x3 window gives this.
# Maybe the chip has a bug where on odd columns, the window pixels are wrong/stale.
# Let me think about the window_3x3 shift register logic.

# The window_3x3 uses 3-deep column shift registers: sr0_0, sr0_1, sr0_2 etc.
# win = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
# This is a LOOK-AHEAD: it shows the window AFTER the current shift.
# After shift: sr0_0<=sr0_1, sr0_1<=sr0_2, sr0_2<=lb0_data
# So the new sr0_2 = lb0_data, new sr0_1 = old sr0_2, new sr0_0 = old sr0_1
# The window (cols c-2,c-1,c) = (new_sr0_0, new_sr0_1, new_sr0_2) = (old sr0_1, old sr0_2, lb0_data)
# That's what win shows. This looks correct.

# But wait — the issue is the TIMING. The controller captures sobel_out when rx_valid
# and row>=2 && col>=2. But col_cnt is the PRE-increment value (pixel_cnt before increment).
# Let me trace the controller timing carefully.

# In the RTL nano_controller:
#   cur_col = pixel_cnt[4:0]  (pre-increment)
#   cur_row = pixel_cnt[10:5]
#   On rx_valid in S_RECV: pixel_cnt <= pixel_cnt+1, and if cur_row>=2 && cur_col>=2: capture sobel_out
#   pixel_shift = accept_pixel = (state==S_RECV or S_IDLE) && rx_valid

# So when pixel_cnt=66 (row=2,col=2), rx_valid arrives:
#   pixel_shift=1, col_cnt=2, row_cnt=2
#   The window assembler shifts with col_cnt=2, row_cnt=2
#   sobel_out is captured (this is out[0])
#   pixel_cnt becomes 67

# When pixel_cnt=67 (row=2,col=3), rx_valid arrives:
#   pixel_shift=1, col_cnt=3, row_cnt=2
#   The window assembler shifts with col_cnt=3, row_cnt=2
#   sobel_out is captured (this is out[1])
#   pixel_cnt becomes 68

# The issue: when the controller captures sobel_out and goes to S_TX_RESULT,
# it STOPS accepting pixels until tx_done. So the next pixel is NOT shifted in
# immediately. This means the streaming is NOT continuous — there's a gap for TX.

# In the golden model, the streaming is continuous — every pixel is accepted,
# and results are emitted. The controller in the golden model also has S_TX_RESULT
# and S_NEXT states... let me check.

# Golden nano_controller: in S_RECV, on rx_valid: _accept_pixel, then if row>=2&&col>=2: capture, go to S_TX_RESULT
# In S_TX_RESULT: tx_start=1, go to S_NEXT
# In S_NEXT: wait for tx_done, then go to S_RECV

# So the golden model ALSO stops accepting during TX! The difference must be elsewhere.
# But the golden functional model (sobel_stream) is continuous — it accepts every pixel.
# The TB uses the functional model (sobel_stream) to generate golden_output.mem.

# So the REAL issue: the RTL controller stops accepting pixels during TX (S_TX_RESULT + S_NEXT),
# but the golden functional model accepts ALL pixels continuously.
# This means the RTL misses pixels! When it's transmitting, incoming UART pixels are lost.

# But wait — the TB sends pixels one at a time and waits. Let me re-read the TB.
# The TB sends a byte, then calls recv_byte (which waits for a result with timeout).
# So the TB pacing is: send pixel, wait for result (or timeout), send next pixel.
# This means pixels are sent slowly enough that TX should complete between sends...

# Actually no. The TB sends a pixel, then immediately tries to recv. But the controller
# only produces a result when row>=2 && col>=2. For the first 66 pixels, no result.
# So recv_byte times out (3 baud periods), then the TB sends the next pixel.
# But during those 3 baud periods of timeout, the controller is in S_RECV waiting.
# When a result IS produced (col>=2,row>=2), the controller goes to S_TX_RESULT,
# and the TB's recv_byte catches it.

# The problem: after the controller captures a result and goes to S_TX_RESULT->S_NEXT,
# it waits for tx_done. During this time, the TB is receiving the byte. After receiving,
# the TB sends the NEXT pixel. But the controller might still be in S_NEXT (waiting tx_done)
# or might have just transitioned to S_RECV.

# KEY ISSUE: The TB sends the next pixel right after recv_byte returns. But recv_byte
# returns after sampling 8 bits + stop bit. The tx_done signal... let me check uart_tx.

print("Need to check uart_tx.v for tx_done timing")