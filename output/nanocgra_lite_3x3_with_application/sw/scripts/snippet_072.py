import sys
sys.path.insert(0, 'golden')
from model.params import CLK_FREQ, BAUD_RATE
DIV = CLK_FREQ // BAUD_RATE
print(f"DIV = {DIV}")

# The test harness samples one-per-clock and indexes bits[0..9] as the 10 frame bits.
# With DIV=434, this can't work. The harness is wrong.
# 
# BUT: the instructions say "Fix the harness and KEEP the assertion's intent."
# The assertion's intent: verify that transmitting 0x3C produces the correct frame 
# (start=0, 8 data bits LSB first, stop=1) and exactly one done pulse.
#
# The correct harness should sample at midpoints: bit k at clock k*DIV + DIV//2
# (relative to when transmission starts).
#
# But there's ALSO a model bug: tx_start is not latched. Even with correct sampling,
# if tx_start arrives on a non-tick cycle, it's dropped.
# 
# Per instructions: "a request pulse (tx_start, write-enable, valid) must be LATCHED 
# when it arrives, not sampled only on a baud/enable tick"
#
# So BOTH need fixing:
# 1. Model: latch tx_start so it's not dropped
# 2. Harness: sample at bit midpoints, not one-per-clock

# Let me verify: with a latched model and correct sampling, would it work?
# Let me simulate a latched version

from model.baud_gen import BaudGen

class UartTxFixed:
    IDLE, START, DATA, STOP = 0, 1, 2, 3
    def __init__(self):
        self.bg = BaudGen()
        self.state = self.IDLE
        self.bit_idx = 0
        self.shreg = 0
        self.tx_out = 1
        self.tx_done = 0
        self.start_req = 0  # latch
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
        # LATCH tx_start when it arrives (regardless of tick)
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
            self.tx_out = 1
            if self.start_req:
                self.shreg = self.start_data
                self.bit_idx = 0
                self.state = self.START
                self.start_req = 0
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

tx = UartTxFixed()
tx.reset()
# idle
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0)
# pulse tx_start
tx.step(1, 1, 1, 0x3C)

# Capture all cycles
all_bits = []
all_dones = []
for i in range(DIV * 12):
    out, done = tx.step(1, 1, 0, 0)
    all_bits.append(out)
    all_dones.append(done)

# Find when transmission starts (first 0 after idle)
# The tx_start is at cycle 2 (0-indexed). First tick after that is at cycle 433.
# At tick 433, state goes IDLE->START, tx_out=0.
# But wait, in my fixed model, at the tick where state transitions IDLE->START,
# tx_out is still set to 1 in the IDLE branch. The START state sets tx_out=0 
# at the NEXT tick. So start bit appears at tick 867, not 433.

# Hmm, let me trace more carefully
print("Checking when tx_out first becomes 0:")
for i, b in enumerate(all_bits):
    if b == 0:
        print(f"  First 0 at cycle {i}")
        break

# Sample at midpoints of each bit period
# Transmission starts when state enters START. Let me find the first 0.
# Actually the issue is the state machine: IDLE->START (at tick), then at NEXT tick 
# START sets tx_out=0 and goes to DATA. So the start bit is emitted one tick late.

# Let me reconsider the state machine. The standard approach:
# IDLE: wait for start_req. When tick+start_req: load shreg, go to START, set tx_out=0
# START: hold tx_out=0 for one bit period. At next tick: go to DATA
# DATA: emit 8 bits, one per tick
# STOP: emit 1, tx_done, go to IDLE

# The current model has the start bit emitted in the START state but only sets tx_out=0
# when ENTERING START (at the tick after IDLE). Actually no - it sets tx_out=0 when 
# IN the START state (at the next tick). So there's a one-tick delay.

# Let me fix: when transitioning IDLE->START, immediately set tx_out=0
print("\nNeed to fix state machine to set tx_out immediately on transition")