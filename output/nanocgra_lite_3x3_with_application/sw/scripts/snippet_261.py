# My "sample one bit late" function was wrong. Let me redo it properly.
# TX sends: start(0), b0, b1, b2, b3, b4, b5, b6, b7, stop(1)
# Each bit lasts BAUD_DIV cycles.
# 
# The tb's recv_byte:
# 1. Wait for data_o to go low (start bit)
# 2. Wait HALF_BAUD + BAUD_DIV cycles (to middle of first data bit)
# 3. Sample 8 bits, each BAUD_DIV apart
#
# The UART TX:
# - On baud_tick in IDLE with start_req: go to START, tx_out=0 (start bit)
# - On next baud_tick in START: tx_out=shreg[0], go to DATA (first data bit)
# - On next baud_tick in DATA: tx_out=shreg[bit_idx], increment bit_idx
# - ... until bit_idx==7, go to STOP
# - On next baud_tick in STOP: tx_out=1, tx_done=1, go to IDLE
#
# So the TX line timing (in baud periods):
# Period 0: start bit (0)
# Period 1: data bit 0
# Period 2: data bit 1
# ...
# Period 8: data bit 7
# Period 9: stop bit (1)
#
# The tb's recv_byte:
# - Detects start bit (data_o=0) at some point during period 0
# - Waits HALF_BAUD + BAUD_DIV = 1.5 baud periods
# - This puts it at the middle of period 1 (data bit 0) - CORRECT
# - Then samples every BAUD_DIV, getting bits at periods 1,2,3,...,8
#
# This should be correct. But what if the start bit detection is off?
#
# The tb detects the start bit when data_o goes from 1 to 0.
# The UART TX sets tx_out=0 on a baud_tick in IDLE->START transition.
# But the baud_tick happens at a specific cycle within the baud period.
#
# The tb's recv_byte samples data_o every posedge clk. It detects the
# start bit when data_o===0 at a posedge. Then it waits HALF_BAUD+BAUD_DIV
# posedges.
#
# The issue: the tb detects the start bit at a random point within the
# start bit period (depending on when the baud_tick fires). If it detects
# it early in the period, the subsequent sampling might be off.
#
# Actually, let me think about this differently. The tb and the UART TX
# share the same clock and same baud_gen. The baud_gen counts 434 cycles
# per baud period. The tb's recv_byte counts cycles too.
#
# The UART TX changes tx_out on baud_ticks. The tb samples data_o on
# posedge clk. The baud_tick is a 1-cycle pulse.
#
# When the UART TX enters START state on a baud_tick, tx_out becomes 0.
# The tb sees data_o=0 on the next posedge clk (1 cycle later).
# Then the tb waits HALF_BAUD+BAUD_DIV = 217+434 = 651 cycles.
# This puts the sampling at cycle baud_tick+1+651.
# The next baud_tick (start of data bit 0) is at cycle baud_tick+434.
# So the tb samples at baud_tick+652, which is 652-434=218 cycles into
# data bit 0's period. That's roughly the middle (217). Good.
#
# Then the tb samples every 434 cycles: baud_tick+652, +1086, +1520, ...
# The data bits change at baud_tick+434, +868, +1302, ...
# So the tb samples at offset 218, 218, 218, ... within each bit period.
# This is consistent and correct.
#
# So the sampling should be fine for a single TX. But what about the
# INTERACTION between send_byte and recv_byte?
#
# The tb sends a pixel (10 baud periods), then calls recv_byte.
# recv_byte waits for data_o to go low. If the controller produces a result,
# the TX starts. But the TX might start WHILE the tb is still sending the
# stop bit of the pixel!
#
# Wait, no. send_byte finishes with a stop bit (data_i=1 for BAUD_DIV cycles).
# Then recv_byte starts. The controller processes the pixel (rx_valid fires
# at the end of send_byte), goes to S_TX_RESULT, and starts TX.
#
# But here's the issue: the UART RX detects the start bit of the NEXT
# byte while the tb is in recv_byte. If the tb's recv_byte takes 10 baud
# periods, and the controller's TX also takes 10 baud periods, they overlap.
# After recv_byte finishes, the tb sends the next pixel. But the controller
# might still be in S_NEXT (waiting for tx_done).
#
# Actually, the TX and recv_byte should finish at about the same time.
# The TX takes 10 baud periods. recv_byte takes ~10 baud periods (detect
# start + 8 bits + stop). So they should be synchronized.
#
# But what if the tb's recv_byte detects the start bit LATE? If the
# controller's TX starts a few cycles after recv_byte begins, recv_byte
# might miss the start bit and time out. Then the tb sends the next pixel.
# The controller is in S_NEXT, so it drops this pixel. Then the tb calls
# recv_byte again, and this time it catches the TX (which is still sending).
# But it catches it in the MIDDLE of the frame, getting garbage.
#
# THIS could explain the pattern! Let me check:
# - Pixel 66 (row=2,col=2): result produced, TX starts
# - tb calls recv_byte, catches TX -> chip[0] = correct
# - Pixel 67 (row=2,col=3): tb sends pixel, controller in S_NEXT, drops it
# - tb calls recv_byte, times out (TX already done)
# - Pixel 68 (row=2,col=4): tb sends pixel, controller back in S_RECV
#   - rx_valid fires, controller captures result, starts TX
#   - tb calls recv_byte, catches TX -> chip[1] = correct result for (2,4)
#
# But chip[1] = 0x9c, not the correct result for (2,4) which is 0x3a.
# And chip[2] = 0x3a which IS the correct result for (2,4).
# So chip[1] is NOT the result for (2,4).
#
# Hmm, this doesn't work either. Let me think again.
#
# Actually, the DBG log shows the controller correctly sends:
# tx_data=44, 38, 3a, 3c, 3e, 3c, 3e, 3c, 3c, 3a, ...
# These are ALL the correct values in order.
# But the tb receives: 44, 9c, 3a, 9e, 3e, 9e, ...
#
# So the controller sends 44, then 38, then 3a, then 3c, ...
# The tb receives 44, then 9c, then 3a, then 9e, ...
#
# The tb receives 44 correctly, then receives 9c instead of 38,
# then receives 3a correctly, then receives 9e instead of 3c.
#
# So every OTHER byte is received incorrectly. The correct bytes
# (44, 3a, 3e, 3e, 3c, ...) are the ones at even indices in the
# controller's output sequence (0th, 2nd, 4th, 6th, 8th, ...).
# The incorrect bytes (9c, 9e, 9e, 9e, 9d, ...) replace the odd-indexed
# ones (1st, 3rd, 5th, 7th, 9th, ...).
#
# This means the tb is receiving the even-indexed TX bytes correctly
# but getting garbage for the odd-indexed ones. The garbage might be
# the odd-indexed bytes received with a timing error.
#
# Let me check: is 0x9c a bit-shifted version of 0x38?
# 0x38 = 0011_1000
# 0x9c = 1001_1100
# If we look at this as a serial stream:
# 0x38 LSB-first: 0,0,0,1,1,1,0,0
# 0x9c LSB-first: 0,0,1,1,1,0,0,1
# 
# 0x38 stream: 0 0 0 1 1 1 0 0
# 0x9c stream: 0 0 1 1 1 0 0 1
# 
# These are the same sequence shifted by 1! 0x9c's bits are 0x38's bits
# shifted left by 1, with a 1 appended at the end.
# 0x38: 0 0 0 1 1 1 0 0
# shift:  0 0 1 1 1 0 0 1  <- this is 0x9c!
# 
# The appended 1 is the STOP bit! So the tb is sampling one bit late,
# catching: b1, b2, b3, b4, b5, b6, b7, stop_bit
# instead of: b0, b1, b2, b3, b4, b5, b6, b7
#
# This means the tb's recv_byte is sampling one baud period too late
# for every other byte!

# Let me verify this for all odd indices:
with open('waves/golden_output.mem') as f:
    glines = f.readlines()
gvals = [int(l.strip(),16) for l in glines if l.strip() and not l.startswith('//')]
with open('waves/chip_output.mem') as f:
    clines = f.readlines()
cvals = [int(l.strip(),16) for l in clines if l.strip() and not l.startswith('//')]

def sample_one_late(byte_val):
    """TX sends start(0), b0..b7, stop(1).
    Sampling 1 late: b1, b2, b3, b4, b5, b6, b7, stop(1)
    """
    bits = [(byte_val >> i) & 1 for i in range(8)]  # b0..b7
    # TX line: start=0, b0, b1, ..., b7, stop=1
    # Normal sample: b0, b1, ..., b7
    # 1-late sample: b1, b2, ..., b7, stop=1
    rx_bits = bits[1:] + [1]  # b1..b7, stop
    rx_byte = sum(rx_bits[i] << i for i in range(8))
    return rx_byte

print("Verifying: chip[odd] = golden[odd] sampled 1 bit late")
all_match = True
for i in range(1, min(40, len(cvals)), 2):
    g = gvals[i]
    c = cvals[i]
    late = sample_one_late(g)
    match = (late == c)
    if not match:
        all_match = False
    print(f"  i={i} golden=0x{g:02x} late=0x{late:02x} chip=0x{c:02x} match={match}")

print(f"\nAll odd indices match '1 bit late' hypothesis: {all_match}")