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

# Progress! Index 0 now matches (44=68? wait, 0x44=68, golden[0]=68. Yes!)
# Even indices match: 44=68, 3a=58, 3e=62, 3e=62, 3c=60, 3c=60, 3c=60, 3a=58, 3a=58, 3c=60
# Odd indices are wrong: 9c=156, 9e=158, 9e=158, 9e=158, 9d=157, 9e=158, 9d=157
# 
# The odd indices have 0x80 set. 156=0x9c, 158=0x9e, 157=0x9d.
# 0x9c - 0x80 = 0x1c = 28. Golden[1] = 0x38 = 56. 28 != 56.
# 0x9e - 0x80 = 0x1e = 30. Golden[3] = 0x3c = 60. 30 != 60.
# Hmm, 28 is half of 56. 30 is half of 60. The odd values are 128 + golden/2!
# 
# 156 = 128 + 28. 56/2 = 28. Yes!
# 158 = 128 + 30. 60/2 = 30. Yes!
# 157 = 128 + 29. 58/2 = 29. Yes!
# 159 = 128 + 31. 62/2 = 31. Yes!
# 
# So odd-indexed outputs = 128 + golden/2. That's bizarre.
# Or equivalently: the odd outputs have an extra 0x80 bit AND are halved.
# 
# This suggests the window for odd columns is getting wrong data.
# The even columns work perfectly. Let me think about what's different for odd columns.
#
# Actually, let me check: maybe the issue is that the controller goes to S_TX_RESULT
# after capturing a result, and during S_TX_RESULT/S_NEXT, the next pixel arrives.
# The pixel_shift is combinational: accept_pixel = (state==IDLE || state==RECV) && rx_valid.
# When state is S_TX_RESULT or S_NEXT, accept_pixel=0, so pixel_shift=0.
# If rx_valid fires during S_TX_RESULT/S_NEXT, the pixel is NOT shifted in.
# But pixel_cnt doesn't increment either (only increments in S_IDLE/S_RECV).
# So the pixel is simply lost!
#
# But the TB sends pixels one at a time and waits for a response.
# When the chip transmits a result, the TB receives it, then sends the next pixel.
# The chip should be back in S_RECV by then.
#
# Wait - the issue is more subtle. When the controller is in S_RECV and gets rx_valid
# with a valid window, it captures sobel_out and goes to S_TX_RESULT.
# The pixel IS accepted (pixel_shift=1, pixel_cnt++).
# But the NEXT pixel: the TB sends it after receiving the result.
# The chip goes S_TX_RESULT (1 cycle) -> S_NEXT (wait for tx_done).
# tx_done fires after UART TX completes (~10 baud periods).
# The TB's recv_byte takes ~10 baud periods. Then the TB sends the next pixel.
# By then, the chip should be in S_RECV.
#
# But what if the chip is in S_NEXT when the next rx_valid fires?
# The UART RX is always running. It detects the start bit and receives the byte.
# rx_valid fires at the end. If the chip is in S_NEXT at that point, the pixel is lost.
#
# The timing: 
# - Chip: S_TX_RESULT (1 cycle) -> S_NEXT (wait tx_done, ~10 baud periods) -> S_RECV
# - TB: recv_byte (~10 baud periods) -> send_byte (~10 baud periods) -> rx_valid fires
# - So from tx_start to next rx_valid: ~20 baud periods.
# - The chip's tx_done fires ~10 baud periods after tx_start.
# - The chip is in S_RECV ~10 baud periods after tx_start.
# - The next rx_valid fires ~20 baud periods after tx_start.
# - So the chip should be in S_RECV when rx_valid fires. No pixel loss.
#
# But wait - the TB's recv_byte might not take exactly 10 baud periods.
# Let me look at the TB's recv_byte more carefully.
# recv_byte: waits for start bit (data_o goes low). Then waits HALF_BAUD + BAUD_DIV,
# then samples 8 bits (8 * BAUD_DIV), then waits BAUD_DIV for stop.
# Total: HALF_BAUD + BAUD_DIV + 8*BAUD_DIV + BAUD_DIV = 10.5 * BAUD_DIV.
# The chip's TX: start (BAUD_DIV) + 8 data (8*BAUD_DIV) + stop (BAUD_DIV) = 10 * BAUD_DIV.
# So recv_byte takes slightly longer than the TX. Good.
#
# Then send_byte: start (BAUD_DIV) + 8 data (8*BAUD_DIV) + stop (BAUD_DIV) = 10 * BAUD_DIV.
# rx_valid fires at the end of the stop bit, so ~10 baud periods after send_byte starts.
#
# Total from tx_start to next rx_valid: 10.5 + 10 = 20.5 baud periods.
# Chip is in S_RECV after ~10 baud periods. So 10.5 baud periods of margin. Should be fine.
#
# So no pixels are lost. The issue must be in the window/line buffer logic.
# The even columns work, odd columns don't. Let me think about what's different.
#
# The window look-ahead: win = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
# For even columns (col 2, 4, 6...): the window uses lb data at col 2, 4, 6...
# For odd columns (col 3, 5, 7...): the window uses lb data at col 3, 5, 7...
# 
# The line buffer is written at col_cnt on pixel_shift. The read is at col_cnt (combinational).
# Both use the SAME col_cnt (combinational from controller). So the read and write are at the same column.
# The read gives the PRE-edge value (old), the write updates it (new).
# This is correct: the window should use the old value (row N-2/N-1) not the new one.
#
# But wait - the line buffer write and the window shift register update happen at the posedge.
# The combinational win uses the PRE-edge lb data and PRE-edge sr values.
# The controller captures sobel_out at the posedge (non-blocking: result_reg <= sobel_out).
# sobel_out is combinational, so it reflects the PRE-edge win. This is correct.
#
# Hmm, but the line buffer write: mem[wr_col] <= pixel_in.
# wr_col = col_cnt (combinational from controller = cur_col).
# pixel_in = rx_byte (combinational from controller).
# At the posedge, mem[cur_col] <= rx_byte. This is correct.
# And lb_rn2: mem[cur_col] <= lb_rn1_rd (pre-edge value of lb_rn1 at cur_col). Correct.
#
# So the line buffer updates are correct. The window should be correct.
# But odd columns are wrong. Let me check if there's a race condition.
#
# Actually, I think the issue might be with the line buffer write for lb_rn2.
# lb_rn2 writes lb_rn1_rd at col_cnt. But lb_rn1_rd is the combinational read of lb_rn1 at col_cnt.
# At the posedge, lb_rn1 also writes: mem[col_cnt] <= pixel_in.
# Since both are non-blocking, lb_rn2 sees the OLD lb_rn1 value. Correct.
#
# Let me check: is the issue that the window_valid signal is wrong?
# window_valid = (col_cnt >= 2) && (row_cnt >= 2)
# col_cnt and row_cnt are combinational from the controller.
# But the controller's validity check uses cur_col and cur_row (same combinational values).
# So they should match.
#
# Wait, the controller checks cur_row >= 2 && cur_col >= 2, and captures sobel_out.
# But sobel_out is from the CGRA which uses win. win is the look-ahead window.
# The look-ahead window uses sr registers (pre-edge) + lb data (pre-edge) + pixel_in.
# This should be the correct window for the current pixel.
#
# Let me check if the issue is that the controller captures sobel_out at the wrong time.
# The controller is in S_RECV. When rx_valid=1 and cur_row>=2 && cur_col>=2:
#   result_reg <= sobel_out
#   state <= S_TX_RESULT
# sobel_out is combinational. At the posedge, result_reg captures the pre-edge sobel_out.
# The pre-edge sobel_out uses the pre-edge win, which uses pre-edge sr + pre-edge lb + pixel_in.
# pixel_in = rx_byte (combinational). So the window includes the current pixel. Correct.
#
# I'm stuck. Let me look at the actual values more carefully.
# Even indices match golden. Odd indices = 128 + golden/2.
# 
# 128 + golden/2... this is like (golden + 256) / 2 or golden/2 + 128.
# In binary: if golden = 0x38 = 0011_1000, then golden/2 = 0001_1100 = 0x1c.
# 128 + 0x1c = 0x9c. The chip output is 0x9c.
# 
# What operation gives 128 + x/2? 
# If we compute (x + 256) / 2 = x/2 + 128. Or (x | 0x80) / something...
# 
# Actually, maybe the window for odd columns has a wrong pixel that causes this.
# Let me check: what if for odd columns, one of the window pixels is wrong?
# 
# The even columns (col 2, 4, 6...) work. The odd columns (col 3, 5, 7...) don't.
# The difference between even and odd: the shift register state.
# After processing col 2: sr = [col0, col1, col2]. Window = [col0, col1, col2] for each row.
# After processing col 3: sr = [col1, col2, col3]. Window = [col1, col2, col3] for each row.
# 
# But the look-ahead window for col 3 is:
# win = {sr0_1, sr0_2, lb0_data, ...} = {col0, col1, lb_rn2[3], ...}
# Wait, sr0_1 = col1 (from col 2's shift), sr0_2 = col2 (from col 2's shift).
# lb0_data = lb_rn2[3] (pre-edge value at col 3).
# So the window for col 3 = [col1, col2, col3] for row N-2. That's correct!
# 
# Hmm, but the sr registers are updated at the posedge. Let me trace more carefully.
# 
# Processing col 2 (pixel at row=2, col=2, idx=66):
# Pre-edge: sr0 = [x, col0, col1] (from previous shifts)
#   Wait, sr0 was updated when col 1 was processed. After col 1:
#   sr0 = [col_prev, col0, col1] where col_prev is from col -1 = 0.
#   Actually, sr0 starts at [0,0,0]. After col 0: sr0 = [0, 0, lb_rn2[0]].
#   After col 1: sr0 = [0, lb_rn2[0], lb_rn2[1]].
#   After col 2: sr0 = [lb_rn2[0], lb_rn2[1], lb_rn2[2]].
# 
# The look-ahead for col 2: win = {sr0_1, sr0_2, lb_rn2[2]} = {lb_rn2[0], lb_rn2[1], lb_rn2[2]}.
# This is [col0, col1, col2] of row N-2. Correct!
# 
# The look-ahead for col 3: pre-edge sr0 = [lb_rn2[0], lb_rn2[1], lb_rn2[2]] (after col 2's shift).
#   win = {sr0_1, sr0_2, lb_rn2[3]} = {lb_rn2[1], lb_rn2[2], lb_rn2[3]}.
# This is [col1, col2, col3] of row N-2. Correct!
# 
# So the window should be correct for both even and odd columns.
# But the output is wrong for odd columns. The issue must be elsewhere.
#
# Let me check: is the controller going to S_TX_RESULT at the right time?
# For col 2 (first valid window): controller captures and goes to S_TX_RESULT.
# Then S_NEXT (wait for tx_done). During this time, the TB is receiving the result.
# Then the TB sends col 3's pixel. The chip should be in S_RECV.
# 
# But what if the chip is NOT in S_RECV when col 3's pixel arrives?
# The chip goes to S_TX_RESULT on the same cycle as col 2's rx_valid.
# Then S_NEXT the next cycle. tx_done fires ~10 baud periods later.
# The TB receives the result (~10.5 baud periods), then sends col 3 (~10 baud periods).
# rx_valid for col 3 fires ~20.5 baud periods after col 2's rx_valid.
# The chip is in S_RECV after ~10 baud periods. So it should be ready.
#
# But here's the issue: when the chip goes to S_TX_RESULT, pixel_shift goes to 0
# (because accept_pixel = (state==IDLE || state==RECV) && rx_valid, and state is now S_TX_RESULT).
# But the pixel at col 2 was already shifted in (pixel_shift was 1 during S_RECV).
# The line buffer and window updated at that posedge. So col 2's data is in the line buffer.
# 
# When col 3's pixel arrives (rx_valid), the chip is in S_RECV.
# pixel_shift = 1, col_cnt = 3, pixel_in = col3's pixel.
# The line buffer writes at col 3, the window shifts.
# The look-ahead window for col 3 should be correct.
#
# I really can't figure this out by reasoning. Let me add some debug output to the TB
# to see what's happening. Actually, let me check if the issue is that the controller
# misses the pixel at col 3 because it's still in S_NEXT.
#
# Let me check the timing more carefully. The TB sends col 2, then calls recv_byte.
# recv_byte waits for the start bit. The chip starts TX in S_TX_RESULT (1 cycle after col 2).
# The TX start bit appears on data_o. recv_byte detects it.
# recv_byte takes 10.5 baud periods. Then the TB sends col 3.
# send_byte takes 10 baud periods. rx_valid fires at the end.
# 
# The chip: S_TX_RESULT (1 cycle) -> S_NEXT. tx_done fires after 10 baud periods.
# Then S_RECV. So the chip is in S_RECV after ~10 baud periods.
# rx_valid for col 3 fires ~20.5 baud periods after col 2. Chip is in S_RECV. OK.
#
# But what about col 4? After col 3, no valid window yet? Wait, col 3 IS a valid window
# (row=2, col=3, both >= 2). So the chip captures col 3's result and goes to S_TX_RESULT.
# Then the TB receives col 3's result, sends col 4. Same timing.
#
# So every pixel from col 2 onwards triggers a TX. The TB receives each one.
# The timing should be fine.
#
# Let me look at this from a different angle. The odd-index outputs = 128 + golden/2.
# What if the sobel_core is computing wrong for certain window values?
# Let me check: what window gives 156 (0x9c)?

# golden[1] = 56. The window for golden[1] is at (row=2, col=3).
# Let me compute the window and check.
def win_at(r,c):
    return [px[r-1][c-1],px[r-1][c],px[r-1][c+1],px[r][c-1],px[r][c],px[r][c+1],px[r+1][c-1],px[r+1][c],px[r+1][c+1]]

w = win_at(2,3)
gx, gy, out = sobel_compute(w)
print(f"Golden window (2,3): {w}, gx={gx}, gy={gy}, out={out}")

# What if one pixel in the window is wrong? Let me try replacing each pixel with 0.
for i in range(9):
    w2 = w.copy()
    w2[i] = 0
    gx2, gy2, out2 = sobel_compute(w2)
    if out2 == cmem[1]:
        print(f"  Replacing pixel {i} with 0 gives {out2} = chip[1]!")

# What if the window has an extra 128 added to one pixel?
for i in range(9):
    w2 = w.copy()
    w2[i] = (w2[i] + 128) & 0xFF
    gx2, gy2, out2 = sobel_compute(w2)
    if out2 == cmem[1]:
        print(f"  Adding 128 to pixel {i} gives {out2} = chip[1]!")