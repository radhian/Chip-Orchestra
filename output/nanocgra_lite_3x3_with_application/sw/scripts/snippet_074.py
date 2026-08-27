import sys
sys.path.insert(0, 'golden')
from model.params import CLK_FREQ, BAUD_RATE
from model.baud_gen import BaudGen
DIV = CLK_FREQ // BAUD_RATE

# The issue: the START state holds tx_out=0 for only 1 tick, then DATA state begins.
# But the start bit should last DIV clocks (one full bit period).
# In the current state machine:
# - Tick 0 (cycle 433): IDLE->START, tx_out=0
# - Tick 1 (cycle 867): START->DATA, tx_out=0 (still start bit in START), then DATA sets tx_out=bit0
# Wait, let me re-read. In START state at tick: tx_out=0, state->DATA.
# In DATA state at tick: tx_out = bit0, bit_idx++.
# So:
# - Tick 0: IDLE->START, tx_out=0 (start bit begins)
# - Tick 1: START->DATA, tx_out=0 (this is STILL the start bit being held? No...)
# 
# The problem: START state sets tx_out=0 and transitions to DATA at the SAME tick.
# So at tick 1, we're in START, set tx_out=0, go to DATA. But we DON'T execute DATA 
# at this tick. At tick 2, we're in DATA, set tx_out=bit0.
# So start bit lasts from tick 0 to tick 1 (1 bit period = DIV clocks). ✓
# Data bit 0 lasts from tick 1 to tick 2. ✓
# ...
# Data bit 7 lasts from tick 8 to tick 9.
# Stop bit at tick 9: STOP state, tx_out=1, tx_done=1.
#
# So the frame is:
# tick 0: start (0)
# tick 1-8: data bits 0-7
# tick 9: stop (1)
# Total 10 ticks = 10*DIV = 4340 cycles
#
# The midpoint sampling should be:
# bit k at tick k, sample at tick_k_start + DIV//2
# tick 0 starts at cycle 433 (first tick after tx_start at cycle 2)
# bit 0 (start): sample at 433 + 434//2 = 433 + 217 = 650
# bit 1 (data0): sample at 433 + 434 + 217 = 1084
# etc.
# In all_bits index (offset by 3): 650-3=647, 1084-3=1081, etc.

# Let me verify with the fixed model
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
                self.tx_out = 0
                self.start_req = 0
            else:
                self.tx_out = 1
        elif self.state == self.START:
            self.tx_out = 0
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
tx.step(1, 1, 1, 0)  # idle cycle 0
tx.step(1, 1, 1, 0)  # idle cycle 1
tx.step(1, 1, 1, 0x3C)  # tx_start cycle 2

all_bits = []
all_dones = []
for i in range(DIV * 12):
    out, done = tx.step(1, 1, 0, 0)
    all_bits.append(out)
    all_dones.append(done)

# Find first 0 (start bit begins)
first_zero = next(i for i, b in enumerate(all_bits) if b == 0)
# first_zero is index in all_bits, which starts at cycle 3
# The start bit begins at cycle first_zero+3
# Bit k midpoint: first_zero + k*DIV + DIV//2
print("0x3C sampled at midpoints:")
sampled = []
for k in range(10):
    idx = first_zero + k * DIV + DIV//2
    sampled.append(all_bits[idx])
print(f"  {sampled}")
print(f"  start={sampled[0]}, data={[sampled[1+b] for b in range(8)]}, stop={sampled[9]}")
val = 0
for b in range(8):
    val |= sampled[1+b] << b
print(f"  reconstructed value: 0x{val:02X} (expected 0x3C)")
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
print("\n0xFF sampled at midpoints:")
sampled2 = []
for k in range(10):
    idx = first_zero2 + k * DIV + DIV//2
    sampled2.append(all_bits2[idx])
print(f"  {sampled2}")
print(f"  sum(dones) = {sum(all_dones2)}")