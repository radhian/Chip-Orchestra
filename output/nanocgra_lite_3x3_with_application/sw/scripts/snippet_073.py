import sys
sys.path.insert(0, 'golden')
from model.params import CLK_FREQ, BAUD_RATE
from model.baud_gen import BaudGen
DIV = CLK_FREQ // BAUD_RATE

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
                self.tx_out = 0  # start bit immediately
                self.start_req = 0
            else:
                self.tx_out = 1
        elif self.state == self.START:
            self.tx_out = 0  # hold start bit
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

# Test with 0x3C
tx = UartTxFixed()
tx.reset()
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0x3C)  # pulse tx_start at cycle 2

all_bits = []
all_dones = []
for i in range(DIV * 12):
    out, done = tx.step(1, 1, 0, 0)
    all_bits.append(out)
    all_dones.append(done)

# Find first 0
first_zero = None
for i, b in enumerate(all_bits):
    if b == 0:
        first_zero = i
        break
print(f"First 0 at cycle {first_zero}")

# The tx_start pulse is at cycle 2 (the 3rd step call).
# all_bits[0] corresponds to cycle 3 (first step after tx_start pulse).
# First tick after tx_start is at cycle 433 (0-indexed from reset).
# But tx_start was at cycle 2, so first tick after that is at cycle 433.
# all_bits index = cycle - 3. So tick at cycle 433 -> all_bits[430].
# At that tick, state IDLE->START, tx_out=0.
# So first_zero should be 430.
print(f"Expected first 0 at all_bits index ~{433-3}")

# Now sample at midpoints
# Bit 0 (start) starts at all_bits[first_zero], lasts DIV clocks
# Bit k starts at all_bits[first_zero + k*DIV]
# Sample at midpoint: all_bits[first_zero + k*DIV + DIV//2]
print("\nSampled bits at midpoints:")
for k in range(10):
    idx = first_zero + k * DIV + DIV // 2
    if idx < len(all_bits):
        print(f"  bit {k}: {all_bits[idx]}")

# Check done pulses
done_cycles = [i for i, d in enumerate(all_dones) if d]
print(f"\nDone pulses at cycles: {done_cycles}")
print(f"sum(dones) = {sum(all_dones)}")