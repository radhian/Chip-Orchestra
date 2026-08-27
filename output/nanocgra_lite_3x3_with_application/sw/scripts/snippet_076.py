import sys
sys.path.insert(0, 'golden')
from model.params import CLK_FREQ, BAUD_RATE
from model.baud_gen import BaudGen
DIV = CLK_FREQ // BAUD_RATE

# I see the problem now. The state machine has an extra tick for the start bit.
# Tick 433: IDLE->START, tx_out=0 (start bit begins)
# Tick 867: START->DATA, tx_out=0 (STILL 0 - start bit held for 2 ticks!)
# Tick 1301: DATA, tx_out=bit0=0
# ...
# The START state sets tx_out=0 AND transitions to DATA. So the start bit is emitted
# at tick 433 (when entering START) and AGAIN at tick 867 (when in START, before going to DATA).
# This means the start bit lasts 2 ticks (2*DIV cycles) instead of 1.
#
# Fix: The START state should NOT set tx_out=0 again. It should just transition to DATA
# and let DATA set the first data bit. OR: merge START into the IDLE transition.
#
# Better fix: remove the START state entirely. When IDLE gets start_req:
# - Load shreg, set tx_out=0 (start bit), go to DATA with bit_idx=-1 (or a separate START state
#   that just transitions to DATA without setting tx_out again)
#
# Actually the cleanest fix: START state transitions to DATA and sets tx_out to bit0.
# No - the start bit needs to be held for one full bit period.
#
# The correct sequence:
# Tick 0: IDLE->START, tx_out=0 (start bit, held for DIV cycles)
# Tick 1: START->DATA, tx_out=bit0 (first data bit, held for DIV cycles)
# Tick 2: DATA, tx_out=bit1
# ...
# Tick 8: DATA, tx_out=bit7
# Tick 9: DATA->STOP, tx_out=1 (stop bit), tx_done=1
#
# So the START state should set tx_out=bit0 (NOT 0) when transitioning to DATA.
# Wait no - at tick 1, we're IN START state. We should transition to DATA and set
# tx_out to the first data bit. But the current code sets tx_out=0 in START.
#
# Fix: In START state, set tx_out = bit0 and go to DATA, increment bit_idx.

class UartTxFixed:
    IDLE, START, DATA, STOP = 0, 1, 2, 3
    def __init__(self):
        self.bg = BaudGen()
        self.state = self.IDLE
        self.bit_idx = 0
        self.shreg = 0
        self.tx_out = 1
        self.tx_done = 0
        self.start_req = 0
        self.start_data = 0
    def reset(self):
        self.bg.reset()
        self.state = self.IDLE
        self.bit_idx = 0
        self.shreg = 0
        self.tx_out = 1
        self.tx_done = 0
        self.start_req = 0
        self.start_data = 0
    def step(self, clk, rst_n, tx_start, data_in):
        self.tx_done = 0
        if clk and rst_n and tx_start:
            self.start_req = 1
            self.start_data = data_in & 0xFF
        tick = self.bg.step(clk, rst_n)
        if not rst_n:
            self.reset()
            return self.tx_out, self.tx_done
        if not tick:
            return self.tx_out, self.tx_done
        if self.state == self.IDLE:
            if self.start_req:
                self.shreg = self.start_data
                self.bit_idx = 0
                self.state = self.START
                self.tx_out = 0  # start bit
                self.start_req = 0
            else:
                self.tx_out = 1
        elif self.state == self.START:
            # Start bit period is over, emit first data bit
            self.tx_out = (self.shreg >> 0) & 1
            self.bit_idx = 1
            self.state = self.DATA
        elif self.state == self.DATA:
            self.tx_out = (self.shreg >> self.bit_idx) & 1
            self.bit_idx += 1
            if self.bit_idx == 8:
                self.state = self.STOP
        elif self.state == self.STOP:
            self.tx_out = 1
            self.tx_done = 1
            self.state = self.IDLE
        return self.tx_out, self.tx_done

# Test 0x3C
tx = UartTxFixed()
tx.reset()
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0x3C)

all_bits = []
all_dones = []
for i in range(DIV * 12):
    out, done = tx.step(1, 1, 0, 0)
    all_bits.append(out)
    all_dones.append(done)

first_zero = next(i for i, b in enumerate(all_bits) if b == 0)
print("0x3C:")
sampled = []
for k in range(10):
    idx = first_zero + k * DIV + DIV//2
    sampled.append(all_bits[idx])
print(f"  sampled: {sampled}")
print(f"  start={sampled[0]}, stop={sampled[9]}")
val = 0
for b in range(8):
    val |= sampled[1+b] << b
print(f"  value: 0x{val:02X} (expected 0x3C)")
print(f"  sum(dones) = {sum(all_dones)}")

# Test 0xFF
tx2 = UartTxFixed()
tx2.reset()
tx2.step(1, 1, 1, 0)
tx2.step(1, 1, 1, 0)
tx2.step(1, 1, 1, 0xFF)
all_bits2 = []
all_dones2 = []
for i in range(DIV * 12):
    out, done = tx2.step(1, 1, 0, 0)
    all_bits2.append(out)
    all_dones2.append(done)
first_zero2 = next(i for i, b in enumerate(all_bits2) if b == 0)
print("\n0xFF:")
sampled2 = []
for k in range(10):
    idx = first_zero2 + k * DIV + DIV//2
    sampled2.append(all_bits2[idx])
print(f"  sampled: {sampled2}")
print(f"  sum(dones) = {sum(all_dones2)}")