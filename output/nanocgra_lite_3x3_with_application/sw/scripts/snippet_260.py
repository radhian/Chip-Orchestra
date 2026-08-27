# KEY FINDING from the sim log:
# The DBG output shows the controller correctly computes sobel=44, 38, 3a, 3c, 3e, 3c, ...
# and tx_data is set to 44, 38, 3a, 3c, 3e, 3c, ...
# These are the CORRECT golden values!
#
# But the chip_output.mem shows: 44, 9c, 3a, 9e, 3e, 9e, ...
# So the controller sends the right data, but the tb receives wrong values
# at odd indices.
#
# This means the bug is in the UART TX or in the tb's recv_byte timing.
# The controller sends: 44, 38, 3a, 3c, 3e, 3c, 3e, 3c, 3c, 3a, ...
# The tb receives:       44, 9c, 3a, 9e, 3e, 9e, 3e, 9e, 3c, 9d, ...
#
# Even indices: 44, 3a, 3e, 3e, 3c, 3c, 3c, 3a, 3c, 3e -> these are
# the CORRECT values at positions 0, 2, 4, 6, 8, 10, 12, 14, 16, 18
# (i.e., every other correct result)
#
# Odd indices: 9c, 9e, 9e, 9e, 9d, 9e, 9d, 9e, 9d, 9f -> wrong
#
# So the tb is receiving: correct[0], garbage, correct[2], garbage, correct[4], ...
# It's SKIPPING every other correct result and receiving garbage instead.
#
# This means the tb's recv_byte is catching an EXTRA byte between each
# correct result. The extra byte has value ~0x9c-0x9f.
#
# What could produce these extra bytes? Let me check:
# 0x9c = 156, 0x9d = 157, 0x9e = 158, 0x9f = 159
# These are suspiciously close to the pixel values in the image (151-170).
#
# HYPOTHESIS: The UART TX is sending the pixel data as well as the result!
# Or: the UART RX echo is happening. But there's no echo path.
#
# Wait - let me look at the UART TX more carefully.
# The controller sets tx_start=1 with tx_data=result for ONE cycle.
# The UART TX latches tx_start and sends the byte.
#
# But what if the UART TX is ALSO sending something else?
# Let me check: does the controller assert tx_start more than once per result?
#
# From the DBG log: "DBG tx_start tx_data=44" appears once per result.
# So tx_start fires once. But the UART TX might be sending extra frames.
#
# Actually, let me reconsider. The tb sends 1024 pixels. For each pixel,
# it calls recv_byte. Most of the time (first 66 pixels), there's no result,
# so recv_byte times out. Then starting at pixel 66 (row=2,col=2), results
# start coming.
#
# The tb flow for each pixel:
# 1. send_byte(pixel) - takes 10 baud periods
# 2. recv_byte - waits for start bit, then captures 10 baud periods
#
# The controller flow:
# 1. rx_valid fires at end of send_byte
# 2. Controller captures result, goes to S_TX_RESULT
# 3. S_TX_RESULT: tx_start=1, go to S_NEXT
# 4. S_NEXT: wait for tx_done
# 5. UART TX sends byte (10 baud periods)
# 6. tx_done fires, controller goes to S_RECV
#
# The tb's recv_byte should catch the TX. But here's the issue:
# The tb's recv_byte has a timeout of 3*BAUD_DIV. If no start bit is
# detected within 3 baud periods, it returns ok=0.
#
# For the first 66 pixels (no result), recv_byte times out after 3 baud periods.
# For pixel 66 (first result), the controller starts TX. But when does the
# start bit appear?
#
# After rx_valid (end of send_byte), the controller takes:
# - 1 cycle to go to S_TX_RESULT
# - 1 cycle in S_TX_RESULT (tx_start=1)
# - Then UART TX waits for next baud tick (up to 434 cycles)
# - Then sends start bit
#
# The tb's recv_byte starts waiting immediately after send_byte.
# It waits up to 3*434 = 1302 cycles. The UART TX start bit comes after
# ~2 cycles + up to 434 cycles = ~436 cycles. So recv_byte should catch it.
#
# After catching the result, recv_byte takes 10 baud periods.
# Then the tb sends the next pixel. By then, the controller should be
# back in S_RECV (tx_done fired).
#
# So the timing should work for a 1:1 correspondence.
# But the chip output shows the tb is receiving extra bytes.
#
# Let me check: what if the UART TX sends a FRAMING ERROR byte?
# Or what if the tb's recv_byte is misaligned and captures bits from
# two different TX frames?
#
# Actually, let me look at the specific values more carefully.
# The correct results are: 44, 38, 3a, 3c, 3e, 3c, 3e, 3c, 3c, 3a, ...
# The chip captures:       44, 9c, 3a, 9e, 3e, 9e, 3e, 9e, 3c, 9d, ...
#
# chip[0]=0x44=01000100 (correct result 0)
# chip[1]=0x9c=10011100
# chip[2]=0x3a=00111010 (correct result 2)
# chip[3]=0x9e=10011110
#
# Let me check: is 0x9c related to 0x38 (the correct result 1)?
# 0x38 = 00111000
# 0x9c = 10011100
# 0x38 << 1 = 01110000 = 0x70. No.
# 0x38 | 0x80 = 10111000 = 0xB8. No.
# 0x9c - 0x38 = 0x64 = 100. Hmm.
# 0x9e - 0x3c = 0x62 = 98.
# 0x9d - 0x3a = 0x63 = 99.
# 0x9f - 0x3e = 0x61 = 97.
# These differences are ~98-100. Not an obvious pattern.
#
# Let me check: is 0x9c = 0x38 + 0x64? 0x64=100.
# Or: 0x9c = 156, 0x38 = 56. 156-56=100.
# 0x9e = 158, 0x3c = 60. 158-60=98.
# 0x9d = 157, 0x3a = 58. 157-58=99.
# 0x9f = 159, 0x3e = 62. 159-62=97.
# Differences: 100, 98, 99, 97. These are close to 100 but vary.
#
# Let me check if the odd values are the correct values PLUS the pixel value
# at that position.
# result[1] = 0x38 = 56, pixel at (2,3) = 170. 56+170=226. No, 0x9c=156.
#
# Let me try: is 0x9c the sobel result of a window that includes the
# CURRENT pixel but with wrong line buffer data?
#
# Actually, let me just check if the odd chip values are the EVEN golden
# values shifted by 1:
with open('waves/golden_output.mem') as f:
    glines = f.readlines()
gvals = [int(l.strip(),16) for l in glines if l.strip() and not l.startswith('//')]
with open('waves/chip_output.mem') as f:
    clines = f.readlines()
cvals = [int(l.strip(),16) for l in clines if l.strip() and not l.startswith('//')]

# Check: chip[2i] = golden[2i] (confirmed)
# Check: chip[2i+1] = golden[2i+1] + something?
# Or: chip[2i+1] = golden[2i] + something?
# Or: chip = [golden[0], X, golden[2], X, golden[4], X, ...]
# meaning the tb captures golden[0], then garbage, then golden[2], ...
# and golden[1], golden[3], ... are lost

# If so, the tb is receiving 2 bytes per result: the correct one and a garbage one.
# The correct ones land at even indices, garbage at odd.
# The golden[1], golden[3] etc. are the CORRECT results that are being
# sent but received as garbage.

# Let me check: is chip[2i+1] a mangled version of golden[2i+1]?
# golden[1]=0x38=00111000, chip[1]=0x9c=10011100
# Bit-reversed 0x38: 00011100 = 0x1C. No.
# 0x38 with bit 7 set: 10111000 = 0xB8. No.
# Complement: ~0x38 = 0xC7. No.

# Let me check if the UART is sending the byte with wrong bit order
# or if the tb is sampling at the wrong time.
# 0x38 = 00111000, LSB first: 0,0,0,1,1,1,0,0
# 0x9c = 10011100, LSB first: 0,0,1,1,1,0,0,1
# These are different. The last bit differs (0 vs 1).
# It looks like 0x9c = 0x38 shifted left by 1 with a 1 shifted in:
# 0x38 = 00111000 -> shift left 1 -> 01110000 = 0x70. No.
# 
# Or 0x9c = 0x38 with bits shifted by 1 position:
# 0x38 = bits: b7=0 b6=0 b5=1 b4=1 b3=1 b2=0 b1=0 b0=0
# 0x9c = bits: b7=1 b6=0 b5=0 b4=1 b3=1 b2=1 b1=1 b0=0
# Not a simple shift.

# Let me try: what if the tb is sampling one bit early or late?
# If the tb samples each bit one baud period too early, it would get
# the previous bit. Let me simulate this.
# TX sends: start(0), b0, b1, b2, b3, b4, b5, b6, b7, stop(1)
# For 0x38 = 00111000, LSB first: b0=0,b1=0,b2=0,b3=1,b4=1,b5=1,b6=0,b7=0
# TX line: 0, 0, 0, 0, 1, 1, 1, 0, 0, 1
# 
# If tb samples one bit late, it gets:
# start detected, then samples: b1=0, b2=0, b3=1, b4=1, b5=1, b6=0, b7=0, stop=1
# Received byte: b0=0,b1=0,b2=1,b3=1,b4=1,b5=0,b6=0,b7=1 = 10011100 = 0x9C!
# 
# THAT'S IT! 0x9c = 0x38 sampled one bit late!

print("EUREKA: chip odd values = golden odd values sampled 1 bit late!")
print("golden[1]=0x38, sampled 1 bit late = 0x9c")
print("golden[3]=0x3c, sampled 1 bit late:")

def sample_one_bit_late(byte_val):
    """Simulate sampling each data bit one position late.
    TX sends: start(0), b0, b1, b2, b3, b4, b5, b6, b7, stop(1)
    Sampling 1 late: gets b1,b2,b3,b4,b5,b6,b7,stop
    """
    bits = [(byte_val >> i) & 1 for i in range(8)]  # b0..b7
    tx_line = [0] + bits + [1]  # start, b0..b7, stop
    # Sample 1 late: positions 2,3,4,5,6,7,8,9 (instead of 1,2,3,4,5,6,7,8)
    rx_bits = [tx_line[i+1] for i in range(8)]  # shift by 1
    rx_byte = sum(rx_bits[i] << i for i in range(8))
    return rx_byte

for i in range(10):
    g = gvals[2*i+1] if 2*i+1 < len(gvals) else 0
    c = cvals[2*i+1] if 2*i+1 < len(cvals) else 0
    late = sample_one_bit_late(g)
    print(f"  golden[{2*i+1}]=0x{g:02x} late=0x{late:02x} chip=0x{c:02x} match={late==c}")