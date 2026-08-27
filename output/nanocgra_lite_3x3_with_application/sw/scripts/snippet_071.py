import sys
sys.path.insert(0, 'golden')
from model.params import CLK_FREQ, BAUD_RATE
DIV = CLK_FREQ // BAUD_RATE
print(f"DIV = {DIV}")
# 434 cycles per bit. The test runs DIV*10+5 = 4345 cycles.
# With tx_start latched, the transmission would take:
# - 1 tick to enter START state (emit start bit=0)
# - 8 ticks for DATA bits
# - 1 tick for STOP bit (emit stop=1, tx_done=1)
# Total = 10 ticks = 10*434 = 4340 cycles
# The test runs 4345 cycles, so there's enough time IF tx_start is latched.
# But tx_start is only sampled on tick, and the pulse is at cycle 2, first tick at 433.
# So tx_start is NEVER seen. The fix: LATCH tx_start when it arrives.

# Also: the test captures bits[0] as start bit. With latching:
# - tx_start arrives at cycle 2, latched
# - At cycle 433 (first tick), state goes IDLE->START, but tx_out is set to 0 in START state
#   Wait, let me re-read the model. In IDLE, if tx_start, go to START. 
#   In START, tx_out=0, go to DATA.
#   So the start bit (0) is emitted during the START state, which begins at tick 433.
#   But the test captures bits from cycle 3 onwards (after the tx_start pulse).
#   bits[0] = cycle 3, bits[1] = cycle 4, ... 
#   The start bit (tx_out=0) would appear at cycle 433 (when tick happens and state->START)
#   But wait, in the current model, when state goes to START at tick 433,
#   tx_out is set to 0 at that same tick. So bits[433-3] = bits[430] would be 0.
#   The test expects bits[0] to be 0 (start bit). That won't work with DIV=434.

# Hmm, the test expects bits[0..9] to be the 10 frame bits.
# But with DIV=434, the start bit doesn't appear until ~430 cycles in.
# So the test harness samples one bit per CLOCK, not one bit per BAUD_PERIOD.
# This is the harness bug described in the instructions!

# Wait, let me re-read the test:
# bits = []
# for _ in range(DIV * 10 + 5):
#     out, done = tx.step(1, 1, 0, 0)
#     bits.append(out)
# It captures one sample per CLOCK for DIV*10+5 = 4345 clocks.
# Then checks bits[0]==0 (start), bits[1..8] = data, bits[9] = stop.
# This samples the START bit 434 times (bits[0..433]), not once!
# bits[0] would be the tx_out value at the first clock after tx_start.
# If tx_start is latched and tx_out goes to 0 immediately (not waiting for tick),
# then bits[0] = 0. But the model only changes tx_out on tick.

# The test is sampling one-per-clock and indexing as if one-per-bit.
# Per the instructions: "sampling a multi-cycle signal once per CLOCK and then 
# indexing the samples as if they were one-per-BIT or one-per-TRANSACTION"
# This is harness bug (b).

# BUT the instructions also say: "For a serial line at CLK/BAUD = D clocks per bit, 
# bit k must be sampled around clock k*D + D//2"
# So the test should sample at the midpoint of each bit period.

# Let me check: is this a harness bug or model bug?
# The test captures bits[0..4344] (one per clock) and checks bits[0..9].
# bits[0] = first clock after tx_start pulse. If the model latches tx_start and 
# immediately drives tx_out=0 (start bit), then bits[0]=0. ✓
# But then bits[1] should be data bit 0. But the model holds start bit for DIV clocks.
# So bits[1] = 0 still (start bit). The test would see bits[1]=0, which for 0x3C 
# data bit 0 = 0. OK that happens to work. But bits[2] should be data bit 1 = 1 (0x3C = 00111100)
# 0x3C = 0b00111100, LSB first: bit0=0, bit1=0, bit2=1, bit3=1, bit4=1, bit5=1, bit6=0, bit7=0
# bits[2] would still be 0 (start bit held for DIV clocks). Expected data bit 1 = 0. OK.
# bits[3] = 0 (still start bit). Expected data bit 2 = 1. FAIL.

# So the test as written can NEVER pass with DIV=434 because it samples one-per-clock.
# This IS a harness bug. The fix: sample at midpoints of each bit period.

print("0x3C =", bin(0x3C))
print("LSB first bits:", [(0x3C>>b)&1 for b in range(8)])