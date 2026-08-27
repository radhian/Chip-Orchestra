import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']
flat = [p for row in px for p in row]
with open('context/golden_ref.json') as f:
    gref = json.load(f)

# The delayed sim matches golden! But the actual chip doesn't match.
# So the issue is NOT the 1-cycle delay on col_cnt. Let me think again.
# 
# The delayed sim works because: when pixel k arrives, col_cnt_reg = (k-1)%32 (from previous cycle).
# But the line buffer write and window read happen with this delayed col_cnt.
# The result is that the window for pixel k uses col (k-1)%32 instead of k%32.
# But somehow this still produces the correct output...
#
# Wait, the delayed sim produces the CORRECT output. That means the 1-cycle delay
# actually doesn't matter for the functional result. But the actual chip doesn't match.
# So there must be ANOTHER issue in the actual RTL that my simulation doesn't capture.
#
# Let me look at the actual chip output more carefully:
# chip: 72, 158, 60, 161, 66, 161, 64, 161, 66, 158
# The odd indices are all ~160 (0xa0). This is suspicious.
# 
# 0xa1 = 161. Let me check what sobel input gives 161.
# The golden values are ~60. 161 is way off.
# 
# Maybe the issue is that the controller goes to S_TX_RESULT and MISSES the next pixel.
# When a valid window is found, the controller captures sobel_out and goes to S_TX_RESULT.
# Then S_NEXT (wait for tx_done). During this time, rx_valid might fire but be ignored.
# The TB sends a pixel, then calls recv_byte. If the chip is transmitting, recv_byte catches it.
# But the next send_byte happens after recv_byte returns.
# 
# The issue: when the controller is in S_TX_RESULT/S_NEXT, it's NOT in S_RECV, so it
# ignores rx_valid. But the TB sends the next pixel right after recv_byte.
# If tx_done hasn't happened yet when the next pixel arrives, the pixel is LOST.
#
# Actually, the TB flow is:
# 1. send_byte(pixel[i])  - takes ~10 baud periods
# 2. recv_byte(rx_byte, rx_ok) - waits up to 3 baud periods for start bit
# 3. If received, capture. If timeout, continue.
# 4. send_byte(pixel[i+1])
#
# The controller:
# - In S_RECV, waits for rx_valid. When it gets one, accepts pixel.
#   If valid window: captures sobel_out, goes to S_TX_RESULT.
# - S_TX_RESULT: tx_start=1 (1 cycle). Goes to S_NEXT.
# - S_NEXT: waits for tx_done.
# - tx_done comes after UART TX finishes (~10 baud periods).
# - Then back to S_RECV.
#
# The TB sends pixel[i] (10 baud periods). Then tries to receive.
# If the chip starts transmitting (because a valid window was found),
# the TB receives the result. This takes ~10 baud periods to receive.
# Then the TB sends pixel[i+1].
# By this time, the chip should be back in S_RECV (tx_done happened during recv).
#
# But what if the chip found a valid window at pixel[i] and is transmitting,
# and the TB's recv_byte catches it, but then the TB immediately sends pixel[i+1]?
# The chip might still be in S_NEXT (waiting for tx_done) or just transitioned to S_RECV.
# If the chip is in S_NEXT when pixel[i+1] arrives, the pixel is LOST.
#
# Actually, the UART TX takes 10 baud periods (start + 8 data + stop).
# The TB's recv_byte also takes 10 baud periods to receive.
# So by the time recv_byte finishes, tx_done should have fired.
# The chip should be back in S_RECV.
#
# But there's a subtlety: the TB's send_byte takes 10 baud periods.
# During send_byte, the UART RX is receiving the bits. rx_valid fires at the END
# of the byte (after the stop bit). So rx_valid fires ~10 baud periods after send_byte starts.
# The controller accepts the pixel, and if valid window, goes to S_TX_RESULT.
# tx_start fires, UART TX starts transmitting. The TB's recv_byte detects the start bit.
# 
# The timing should work. But let me check: does the controller miss pixels because
# it's in S_TX_RESULT/S_NEXT when the next rx_valid fires?
#
# The TB sends pixel[i], then calls recv_byte. recv_byte waits for the start bit.
# If the chip is transmitting, it catches the byte (10 baud periods).
# Then the TB sends pixel[i+1] (10 baud periods).
# The chip's UART RX receives pixel[i+1] over 10 baud periods.
# rx_valid fires at the end. By then, the chip should be in S_RECV.
#
# But what if NO valid window was found for pixel[i]? Then the chip stays in S_RECV.
# The TB's recv_byte times out (3 baud periods). Then sends pixel[i+1].
# The chip receives pixel[i+1] while in S_RECV. OK.
#
# The issue might be that when a valid window IS found, the chip goes to S_TX_RESULT
# and then S_NEXT. During S_NEXT, it waits for tx_done. But the TB's recv_byte
# might finish BEFORE tx_done (if the TB's baud timing is slightly off).
# Then the TB sends the next pixel, which arrives while the chip is in S_NEXT.
# The pixel is lost!
#
# Actually, the TB's recv_byte samples at the SAME baud rate as the chip's TX.
# So recv_byte takes exactly as long as the TX. When recv_byte finishes,
# the stop bit is done, and tx_done fires. So the chip transitions to S_RECV
# at the same time the TB finishes receiving. Then the TB sends the next pixel.
# There might be a race condition.
#
# Let me check: after recv_byte finishes, the TB immediately calls send_byte.
# send_byte sets data_i=0 (start bit) and waits BAUD_DIV cycles.
# The chip's UART RX needs to detect this start bit.
# But the chip might still be in S_NEXT (if tx_done hasn't fired yet).
# Even if the chip is in S_NEXT, the UART RX is still running and will detect
# the start bit. But the controller won't accept rx_valid until it's back in S_RECV.
# So the byte is received by UART RX but ignored by the controller!
# 
# This is the bug: pixels are being lost when the controller is in S_TX_RESULT/S_NEXT.
# The UART RX receives the byte and pulses rx_valid, but the controller ignores it.
#
# The fix: either buffer the received pixel, or don't send the next pixel until
# the chip is ready. But we can't change the TB (it's the test).
# 
# Actually wait - the TB calls recv_byte AFTER every send_byte. If the chip
# transmits a result, recv_byte catches it (10 baud periods). If not, recv_byte
# times out (3 baud periods). Then the TB sends the next pixel.
# 
# When the chip transmits: send_byte(10) + recv_byte(10) = 20 baud periods between pixels.
# The chip: rx_valid at end of send_byte. Goes to S_TX_RESULT(1 cycle) -> S_NEXT.
# S_NEXT waits for tx_done. tx_done fires after UART TX (10 baud periods).
# So the chip is in S_NEXT for ~10 baud periods. Then back to S_RECV.
# The TB's recv_byte also takes 10 baud periods. So by the time the TB sends
# the next pixel, the chip should be in S_RECV. Timing should work.
#
# But when NO result is transmitted: send_byte(10) + recv_byte_timeout(3) = 13 baud periods.
# The chip stays in S_RECV the whole time. No issue.
#
# Hmm, but the first valid window is at pixel 66 (idx=66, row=2, col=2).
# Before that, no results. The TB sends 66 pixels, each followed by a 3-baud timeout.
# Then at pixel 66, the chip finds a valid window and transmits.
# The TB receives it. Then sends pixel 67. The chip should be in S_RECV.
# 
# But wait - the controller in S_RECV checks rx_valid. When it finds a valid window,
# it captures sobel_out and goes to S_TX_RESULT. But it ALSO accepted the pixel
# (pixel_shift=1, pixel_cnt++). So the pixel is NOT lost. The issue is the NEXT pixel.
# 
# After going to S_TX_RESULT -> S_NEXT, the controller is NOT in S_RECV.
# If the next pixel arrives during S_TX_RESULT or S_NEXT, it's lost.
# 
# The TB sends pixel 66, then recv_byte (catches the result, 10 baud periods).
# Then sends pixel 67 (10 baud periods). The chip's UART RX receives pixel 67.
# rx_valid fires at the end of byte 67. By then, the chip should be back in S_RECV
# (tx_done fired during recv_byte, which took 10 baud periods).
# 
# But there's a timing issue: the chip's tx_done fires when the STOP bit is sent.
# The TB's recv_byte detects the stop bit at the same time (roughly).
# Then the TB starts send_byte for pixel 67. The start bit is sent.
# The chip's UART RX detects the start bit. But the chip might still be in S_NEXT
# for a few cycles after tx_done (it transitions to S_RECV on the NEXT clock after tx_done).
# 
# Actually, in S_NEXT: if (tx_done) state <= S_RECV. So the transition happens at
# the posedge after tx_done. tx_done is a 1-cycle pulse. So the chip transitions to
# S_RECV one cycle after tx_done. The UART RX takes 10 baud periods to receive the
# next byte. So by the time rx_valid fires, the chip is definitely in S_RECV.
#
# So pixels shouldn't be lost. Let me look at the actual mismatch pattern more carefully.

# The chip output has 900 values (correct count). So no pixels are lost.
# The issue is the VALUES are wrong, with an alternating pattern.

# Let me check: is the alternating pattern related to even/odd output indices?
# Output index 0 = window at (row=2, col=2) -> even col
# Output index 1 = window at (row=2, col=3) -> odd col
# The odd output indices have high values (~160). Even indices are closer to golden.

# What if the line buffer read is wrong for odd columns?
# The col_cnt is registered. When the controller sets col_cnt <= cur_col,
# the line buffer uses the NEW col_cnt (combinational read) but writes at the NEW col_cnt too.
# Wait - the line buffer write uses wr_col which is col_cnt (registered).
# At the posedge: col_cnt updates to cur_col. The line buffer write happens at the same posedge.
# Does the line buffer write use the OLD or NEW col_cnt?
# In Verilog, non-blocking assignments: col_cnt <= cur_col means col_cnt gets cur_col at the END
# of the time step. The line_buffer's always block also uses non-blocking: mem[wr_col] <= pixel_in.
# wr_col is connected to col_cnt. Since col_cnt is updated by non-blocking assignment,
# the line buffer sees the OLD col_cnt value (non-blocking semantics: all RHS evaluated first,
# then all LHS updated). So the line buffer writes at the OLD col_cnt!
# 
# But the line buffer READ (rd_data = mem[rd_col]) is combinational. rd_col = col_cnt.
# At the time of the combinational read (during the cycle), col_cnt has its current registered value.
# 
# So: the line buffer writes at OLD col_cnt, but reads at OLD col_cnt too (combinational, same cycle).
# The window uses the read value (OLD col_cnt). This is consistent.
# But the write goes to the WRONG column (OLD col_cnt instead of NEW cur_col).
#
# This is the 1-cycle delay issue. The col_cnt registered output lags by one cycle.
# When pixel k arrives, col_cnt is still (k-1)%32 from the previous cycle.
# The line buffer writes pixel k at column (k-1)%32 instead of k%32.
# 
# But my delayed simulation showed this produces the CORRECT output!
# Let me re-check...

# Actually, in my delayed sim, I had the line buffer write at the delayed col_cnt,
# and the window read at the delayed col_cnt. And it matched golden.
# But in the actual RTL, there's an additional complication:
# the controller checks cur_row >= 2 && cur_col >= 2 for validity,
# but the line buffer/window use the delayed col_cnt/row_cnt.
# So the validity check uses the CURRENT col/row, but the data uses the DELAYED col/row.
# This mismatch could cause the alternating pattern!

# In my delayed sim, I used the delayed col/row for BOTH the validity check AND the data.
# But the actual RTL uses cur_col/cur_row for the validity check (in the controller)
# and delayed col_cnt/row_cnt for the data (line buffer/window).
# 
# Let me simulate this mismatch:
def rtl_sim_mismatch(pixels):
    """Simulate RTL with delayed col_cnt for data but current col/row for validity."""
    lb_rn2 = [0]*32
    lb_rn1 = [0]*32
    sr0 = [0,0,0]
    sr1 = [0,0,0]
    sr2 = [0,0,0]
    results = []
    pixel_cnt = 0
    col_cnt_reg = 0
    row_cnt_reg = 0
    pixel_in_reg = 0
    pixel_shift_reg = 0
    
    for idx, px in enumerate(pixels):
        px = int(px) & 0xFF
        cur_col = pixel_cnt % 32
        cur_row = pixel_cnt // 32
        
        # The controller checks validity using cur_col/cur_row (combinational wire)
        # But the data path uses col_cnt_reg/row_cnt_reg (delayed)
        
        # Data path uses delayed values
        active_col = col_cnt_reg
        active_row = row_cnt_reg
        active_shift = pixel_shift_reg
        active_pixel = pixel_in_reg
        
        if active_shift:
            rn2 = lb_rn2[active_col] if active_row >= 2 else 0
            rn1 = lb_rn1[active_col] if active_row >= 1 else 0
            
            win = [sr0[1], sr0[2], rn2,
                   sr1[1], sr1[2], rn1,
                   sr2[1], sr2[2], active_pixel]
            
            # Validity check uses cur_col/cur_row (the controller's combinational check)
            # But the controller captures sobel_out when cur_row>=2 && cur_col>=2
            # AND the state machine is in S_RECV with rx_valid
            # The sobel_out is from the window using delayed col/row
            if cur_row >= 2 and cur_col >= 2:
                gx, gy, out = sobel_compute(win)
                results.append(out)
            
            # Update line buffers at delayed col
            if active_row >= 1:
                lb_rn2[active_col] = lb_rn1[active_col]
            lb_rn1[active_col] = active_pixel
            
            sr0 = sr0[1:] + [rn2]
            sr1 = sr1[1:] + [rn1]
            sr2 = sr2[1:] + [active_pixel]
        
        # Update registered outputs
        col_cnt_reg = cur_col
        row_cnt_reg = cur_row
        pixel_in_reg = px
        pixel_shift_reg = 1
        pixel_cnt += 1
    
    return results

results = rtl_sim_mismatch(flat)
print("Mismatch sim first 20:", results[:20])
print("Chip first 20:        ", cmem[:20])
print("Match chip?", results[:20] == cmem[:20])