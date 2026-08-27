# The pattern is: even indices match golden, odd indices don't.
# Even: 0x44, 0x3a, 0x3e, 0x3e, 0x3c, 0x3c, 0x3c, 0x3a, 0x3c, 0x3e  (matches golden)
# Odd:  0x9c, 0x9e, 0x9e, 0x9e, 0x9d, 0x9e, 0x9d, 0x9e, 0x9d, 0x9f  (doesn't match)
#
# The odd values are ~0x9e = 158. Let me check if these are sobel results
# computed one cycle late (from the PREVIOUS window) or something.
#
# Actually, let me think about this differently. The testbench sends a pixel,
# then immediately tries to receive. The controller goes:
#   S_RECV -> (rx_valid) -> capture result -> S_TX_RESULT -> S_NEXT -> wait tx_done -> S_RECV
#
# The TX takes many cycles (10 baud periods). During TX, the controller is in
# S_NEXT and won't accept new pixels. So the testbench's recv_byte will
# capture the TX output.
#
# But here's the issue: the testbench sends a pixel, then calls recv_byte.
# recv_byte waits for data_o to go low (start bit). If the controller doesn't
# produce a result for this pixel (because row<2 or col<2), data_o stays high
# and recv_byte times out (3 baud periods). Then the tb sends the next pixel.
#
# For the first result (row=2, col=2), the controller captures and sends.
# The tb receives it as chip_out[0].
#
# For the next pixel (row=2, col=3), the controller should capture and send
# another result. But the controller is in S_TX_RESULT/S_NEXT while sending
# the previous result. It won't accept this pixel until it returns to S_RECV.
#
# So the controller DROPS pixels while it's sending! This means:
# - When the tb sends pixel for (2,3), the controller is busy sending result[0]
# - The pixel is lost (rx_valid fires but controller is in S_NEXT, not S_RECV)
# - The tb's recv_byte captures the TX of result[0]... but wait, it already
#   captured that.
#
# Actually, let me re-read the tb flow more carefully.
# The tb sends pixel[i], then calls recv_byte.
# recv_byte waits up to 3*BAUD_DIV cycles for a start bit.
# If the controller is sending a result, recv_byte catches it.
# If not, recv_byte times out.
#
# The problem: the controller takes ~10 baud periods to send one result.
# During that time, the tb is blocked in recv_byte. After recv_byte returns,
# the tb sends the next pixel. But the controller might have missed several
# rx_valid pulses during the TX.
#
# Wait, no. The tb sends pixels ONE AT A TIME, waiting for each send_byte
# to complete (10 baud periods each). Between sends, it calls recv_byte.
# So the controller sees rx_valid once every ~10 baud periods (when a byte
# finishes receiving). The controller should be back in S_RECV by then.
#
# Let me think about the timing more carefully.
# send_byte takes 10 baud periods. During this time, the UART RX is receiving.
# At the end of send_byte, rx_valid pulses for 1 cycle.
# Then the tb calls recv_byte, which waits for data_o to go low.
#
# If the controller produced a result, it starts TX. The TX start bit comes
# after the controller goes through S_TX_RESULT (1 cycle) -> S_NEXT.
# In S_TX_RESULT, tx_start=1. The UART TX latches this and starts sending
# on the next baud tick.
#
# The issue might be that the controller captures the WRONG sobel_out value.
# Let me check: when rx_valid fires, the controller is in S_RECV.
# It does: pixel_cnt <= pixel_cnt + 1, and if cur_row>=2 && cur_col>=2,
# it captures sobel_out.
#
# But sobel_out is combinational from win, and win depends on the CURRENT
# pixel_shift, col_cnt, row_cnt, pixel_in, and the line buffer reads.
# All of these are combinational from rx_valid.
#
# When rx_valid fires:
#   pixel_in = rx_byte (combinational)
#   pixel_shift = 1 (combinational, because state==S_RECV && rx_valid)
#   col_cnt = pixel_cnt[4:0] (combinational)
#   row_cnt = pixel_cnt[10:5] (combinational)
#
# The window module's win output is combinational:
#   win = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
#
# lb0_data = mem_rn2[col_cnt] (combinational read)
# lb1_data = mem_rn1[col_cnt] (combinational read)
#
# So win is the look-ahead window for the current pixel. sobel_out is computed
# from this. The controller captures sobel_out into result_reg.
#
# This should be correct. But the even/odd pattern suggests something is
# off by one in the pixel stream.
#
# KEY INSIGHT: The controller DROPS pixels when it goes to S_TX_RESULT!
# When a result is produced (row>=2, col>=2), the controller goes to
# S_TX_RESULT, then S_NEXT. While in these states, it does NOT accept
# new pixels (accept_pixel is only true in S_IDLE or S_RECV).
#
# So after producing result for pixel at (2,2), the controller goes to
# S_TX_RESULT. The next pixel from the tb (for (2,3)) arrives as rx_valid,
# but the controller is in S_TX_RESULT or S_NEXT, so it's DROPPED.
#
# The tb sends pixel for (2,3), gets no result (recv_byte times out),
# then sends pixel for (2,4). By now the controller might be back in S_RECV.
# So the controller processes (2,2) -> result, drops (2,3), processes (2,4) -> result, ...
#
# This means the controller only produces results for EVEN columns!
# And the tb captures them alternately: result, timeout, result, timeout...
# But the tb stores every received byte sequentially in chip_out[].
# So chip_out[0] = result for (2,2), chip_out[1] = result for (2,4), etc.
#
# But that doesn't match either, because chip[1]=0x9c which is NOT the
# golden result for (2,4) which is 0x3a (and chip[2]=0x3a matches golden[2]).
#
# Hmm wait. Let me re-examine. The tb sends 1024 pixels. For each, it calls
# recv_byte. Most of the time (row<2 or col<2), recv_byte times out.
# When row>=2 and col>=2, the controller produces a result.
#
# But the controller drops the next pixel while sending. So:
# - pixel (2,2): result produced -> captured as chip[0]
# - pixel (2,3): DROPPED (controller in S_TX_RESULT/S_NEXT)
#   - recv_byte times out (no result for this pixel)
# - pixel (2,4): controller back in S_RECV, result produced -> captured as chip[1]
#   BUT the controller's pixel_cnt is now wrong! It missed (2,3), so
#   pixel_cnt is at (2,3) when it processes (2,4)'s data.
#
# Actually no. pixel_cnt increments on EVERY accepted pixel. Since (2,3) was
# dropped, pixel_cnt doesn't increment for it. So when (2,4) arrives:
#   pixel_cnt is still at the value for (2,3) [because (2,3) was dropped]
#   cur_col = 3, cur_row = 2
#   The controller accepts this pixel, pixel_cnt becomes (2,4)
#   But the pixel DATA is from (2,4), while the line buffers think it's at col 3!
#
# This is the bug! The controller drops pixels during TX, causing a
# misalignment between the pixel data and the column/row counters.
#
# Actually wait, let me reconsider. Does the controller really drop pixels?
# The UART RX has a buffer? No, rx_valid is a 1-cycle pulse. If the
# controller is not in S_RECV, the pulse is lost.
#
# But the tb sends pixels synchronously - it waits for send_byte to finish,
# then calls recv_byte. The send_byte takes 10 baud periods. The TX also
# takes 10 baud periods. So by the time the tb finishes recv_byte (capturing
# the TX output) and sends the next pixel, the controller should be done
# with TX and back in S_RECV.
#
# Let me trace the timing more carefully:
# 1. tb sends pixel (2,2) via send_byte (10 baud periods)
# 2. At end of send_byte, rx_valid pulses
# 3. Controller in S_RECV: accepts pixel, captures result, goes to S_TX_RESULT
# 4. tb calls recv_byte
# 5. Controller: S_TX_RESULT (1 cycle) -> tx_start=1 -> S_NEXT
# 6. UART TX latches tx_start, waits for baud tick, sends 10 bits
# 7. recv_byte catches the TX, takes 10 baud periods
# 8. After recv_byte, tb sends next pixel (2,3)
# 9. By now, TX should be done, controller back in S_RECV
#
# So the controller should NOT drop pixels. The timing works out because
# send_byte and recv_byte each take ~10 baud periods, and the controller
# finishes TX in that time.
#
# But wait - there's a subtlety. After the controller captures the result
# and goes to S_TX_RESULT, it takes 1 cycle to set tx_start. Then the UART TX
# waits for the next baud tick. The baud tick might not come for up to 434
# cycles. Then TX takes 10 baud periods = 4340 cycles.
#
# Meanwhile, recv_byte in the tb waits for data_o to go low. data_o goes low
# when the UART TX starts sending the start bit. This happens at the next
# baud tick after tx_start is asserted.
#
# So recv_byte should catch the TX. After recv_byte finishes (10 baud periods),
# the controller should be back in S_RECV (tx_done fires at the end of TX).
#
# The timing should work. So why the mismatch?
#
# Let me look at this from yet another angle. Let me check if the chip is
# producing the right NUMBER of results. chip_output.mem has 900 values
# (plus a comment line). So it produces exactly 900 results. Good.
#
# But 450 match (even indices) and 450 don't (odd indices). This is exactly
# half. This strongly suggests the controller is dropping every other pixel
# and producing results for only half the windows, but the tb is capturing
# something for the other half.
#
# OR: the controller produces all 900 results correctly, but every other
# result is wrong.
#
# Let me check: are the even-index chip values the correct golden values
# for the even-index windows? Yes, we confirmed that.
# Are the odd-index chip values the correct golden values for any windows?
# 0x9c doesn't appear in the first 30 golden values at all.
#
# Let me check if the odd chip values are the sobel results of windows
# that are shifted by one ROW (using row N-1, N, N+1 instead of N-2, N-1, N).

# Actually, let me just check: what if the line buffer chain has a bug
# where lb_rn2 gets the wrong data?
# In the RTL top:
#   u_lb_rn1: pixel_in=pixel_in, wr_col=col_cnt -> stores current pixel
#   u_lb_rn2: pixel_in=lb_rn1_rd, wr_col=col_cnt -> stores old rn1 value
#
# lb_rn1_rd = mem_rn1[col_cnt] (combinational, OLD value before write)
# This is correct: rn2 gets the old rn1, rn1 gets the new pixel.
#
# But wait - there's a timing issue! Both line buffers write on the SAME
# clock edge (pixel_shift). The rn2 buffer reads lb_rn1_rd (combinational,
# old value) and writes it. The rn1 buffer writes pixel_in. Both happen
# simultaneously. Since lb_rn1_rd is the OLD value, rn2 gets the correct
# old rn1 value. This is fine.
#
# Let me try a completely different hypothesis: the UART is corrupting
# every other byte. Let me check if the odd chip values are the even
# chip values with some bit transformation.

with open('waves/chip_output.mem') as f:
    clines = f.readlines()
cvals = [int(l.strip(),16) for l in clines if l.strip() and not l.startswith('//')]

# Check: is chip[1] = chip[0] + something?
print("chip[0]=%d chip[1]=%d diff=%d" % (cvals[0], cvals[1], cvals[1]-cvals[0]))
print("chip[2]=%d chip[3]=%d diff=%d" % (cvals[2], cvals[3], cvals[3]-cvals[2]))
print("chip[4]=%d chip[5]=%d diff=%d" % (cvals[4], cvals[5], cvals[5]-cvals[4]))

# Check: is chip[odd] = pixel value at that position?
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
px = grid['pixels']
# pixel at (2,3) = px[2][3] = 170
print("px[2][3]=%d chip[1]=%d" % (px[2][3], cvals[1]))
print("px[2][5]=%d chip[3]=%d" % (px[2][5], cvals[3]))

# Hmm, 170 vs 156. Not matching directly.
# Let me check if chip[odd] = sobel of window at (row, col) but with
# the window shifted by 1 column to the right (col+1 instead of col)
# That would mean the window uses columns c-1, c, c+1 instead of c-2, c-1, c

# Actually, let me check a simpler hypothesis:
# What if the chip is computing sobel on the RIGHT window but the UART TX
# is sending the wrong byte? Like it's sending the pixel instead of the result?
# Or it's sending result_reg from the wrong cycle?

# Let me check: what's the sobel result if we use a DEGENERATE window
# where the top row (N-2) equals the bottom row (N)?
# This would happen if lb_rn2 is actually getting current-row data.

# Simulate with rn2 = rn1 (both line buffers have the same data)
import sys
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute

IMG_W = 32
lb_rn1 = [0] * IMG_W
wcols = [[0, 0, 0] for _ in range(3)]
results_rn2_eq_rn1 = []
for idx, pxx in enumerate(pixels):
    row = idx // IMG_W
    col = idx % IMG_W
    pxx = int(pxx) & 0xFF
    rn1 = lb_rn1[col] if row >= 1 else 0
    rn2 = rn1  # BUG: rn2 = rn1 instead of old rn1
    for r in range(3):
        wcols[r] = wcols[r][1:] + [0]
    wcols[0][2] = rn2
    wcols[1][2] = rn1
    wcols[2][2] = pxx
    lb_rn1[col] = pxx
    if col >= 2 and row >= 2:
        w = [wcols[r][c] for r in range(3) for c in range(3)]
        out = sobel_compute(w)[2]
        results_rn2_eq_rn1.append(out)

print("\nWith rn2=rn1 (bug): first 20:", [hex(x) for x in results_rn2_eq_rn1[:20]])
print("chip                first 20:", [hex(x) for x in cvals[:20]])