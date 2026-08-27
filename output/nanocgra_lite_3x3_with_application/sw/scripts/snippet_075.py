import sys
sys.path.insert(0, 'golden')
from model.params import CLK_FREQ, BAUD_RATE
from model.baud_gen import BaudGen
DIV = CLK_FREQ // BAUD_RATE

# The start bit is being held for 2 ticks (both IDLE->START tick and START->DATA tick 
# set tx_out=0). Let me trace tick by tick.

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
            self.tx_out = 0  # THIS IS THE PROBLEM - start bit held for 2 ticks
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
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0x3C)

# Trace ticks
tick_count = 0
for i in range(DIV * 12):
    out, done = tx.step(1, 1, 0, 0)
    # Check if this was a tick by monitoring bg.cnt
    was_tick = (tx.bg.cnt == 0)  # after tick, cnt resets to 0
    # Actually let me check differently
    if done:
        print(f"cycle {i+3}: DONE, tx_out={out}, state={tx.state}")
    
# Let me trace state at each tick
tx2 = UartTxFixed()
tx2.reset()
tx2.step(1, 1, 1, 0)
tx2.step(1, 1, 1, 0)
tx2.step(1, 1, 1, 0x3C)

prev_state = -1
for i in range(DIV * 12):
    old_cnt = tx2.bg.cnt
    out, done = tx2.step(1, 1, 0, 0)
    # Detect tick: cnt went from DIV-1 to 0, or cnt is 0 and was not 0 before... 
    # Actually tick happens when cnt==DIV-1, then cnt resets to 0
    # So after a tick, cnt=0. Before tick, cnt=DIV-1.
    # If old_cnt == DIV-1, this was a tick.
    if old_cnt == DIV - 1:
        print(f"Tick at cycle {i+3}: state={tx2.state}, tx_out={out}, bit_idx={tx2.bit_idx}")