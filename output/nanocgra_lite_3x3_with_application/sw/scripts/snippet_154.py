import json
import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# Perfect! The pattern is: reset + 3 warmup cycles before each frame.
# Frame starts: 430, 5643, 10856, 16069
# Reset at: start-430-3 = start-433
# Frame 1: reset at -433 (before vec 0), warmup at -3, first tick at 430
# Frame 2: reset at 5643-433=5210, warmup at 5210, first tick at 5643
# Frame 3: reset at 10856-433=10423, warmup at 10423, first tick at 10856
# Frame 4: reset at 16069-433=15636, warmup at 15636, first tick at 16069

# But for the TB, we can't have negative cycles. So for frame 1:
# reset at cycle 0 (vec 0), deassert at cycle 3, tx_start=1 at cycle 3, data=60
# first tick at 3+430=433. But frame 1 starts at 430. Off by 3.
# 
# OR: reset for 3 cycles (vec 0,1,2), deassert at vec 3, tx_start=1 at vec 3.
# baud_gen starts at vec 3. First tick at vec 3+433=436. Frame at 436. Off by 6.
#
# The issue: the golden model with 3 warmup has the baud_gen running during warmup.
# warmup -3: bg cnt=0
# warmup -2: bg cnt=1
# warmup -1: bg cnt=2
# vec 0: bg cnt=3
# ...
# vec 430: bg cnt=433 -> tick
#
# So the baud_gen starts at warmup -3, which is 3 cycles before vec 0.
# In the TB, we need the baud_gen to start 3 cycles before vec 0.
# 
# TB approach:
# - Assert reset (rst_n=0) for 2 cycles (warmup -3, -2)
# - Deassert reset (rst_n=1) at warmup -1 (cycle before vec 0)
# - Pulse tx_start=1 at warmup -1
# - vec 0 starts
# 
# Wait, the reset_sync in the top module adds 2 cycles. But for the unit TB,
# we drive rst_n directly.
# 
# For the uart_tx unit TB:
# - rst_n=0 for first 2 cycles (let's call them -3, -2)
# - At cycle -1: rst_n=1, tx_start=1, data_in=60
# - At cycle 0 (vec 0): rst_n=1, tx_start=0
# - baud_gen starts counting from cycle -1 (when rst_n=1)
# - cnt at vec 0: 1 (counted 1 cycle since reset)
# - cnt at vec 430: 1+430=431. Not 433.
# 
# Hmm, that gives tick at vec 432 (cnt=433). Off by 2.
#
# Let me try: rst_n=0 for 1 cycle (-3), rst_n=1 at -2, tx_start=1 at -2.
# baud_gen starts at -2. cnt at vec 0: 2. cnt at vec 430: 432. Tick at 431. Off by 1.
#
# Try: rst_n=0 for 0 cycles. rst_n=1 at -3. tx_start=1 at -3.
# baud_gen starts at -3. cnt at vec 0: 3. cnt at vec 430: 433. Tick at 430. Match!
#
# So: NO reset at all. Just start with rst_n=1, tx_start=1 at cycle -3.
# But we need 3 warmup cycles before vec 0.
# 
# TB approach:
# - cycle -3: rst_n=1, tx_start=1, data_in=60
# - cycle -2: rst_n=1, tx_start=0
# - cycle -1: rst_n=1, tx_start=0
# - cycle 0 (vec 0): start checking
#
# But the TB can't have negative cycles. We can use an initial block:
# initial begin
#   rst_n = 1; tx_start = 1; data_in = 60;
#   @(posedge clk); // cycle -3
#   tx_start = 0;
#   @(posedge clk); // cycle -2
#   @(posedge clk); // cycle -1
#   // now at cycle 0 (vec 0)
#   for (i=0; i<N; i++) begin
#     // check outputs
#     @(posedge clk);
#   end
# end
#
# But the outputs are checked AFTER the posedge. So:
# - After posedge at cycle -3: tx_start was 1, start_req latched. baud_gen cnt=1.
# - After posedge at cycle -2: cnt=2.
# - After posedge at cycle -1: cnt=3.
# - After posedge at cycle 0 (vec 0): cnt=4. Check outputs: tx_out=1 (idle). Expected=1. OK.
# - ...
# - After posedge at cycle 430 (vec 430): cnt=433. tick=1. IDLE->START. tx_out=0. Expected=0. OK.
#
# Wait, the golden model step() is called once per cycle and returns the output
# AFTER the step. In the TB, we check after posedge clk. So:
# - Set inputs BEFORE posedge
# - posedge clk (DUT updates)
# - Check outputs AFTER posedge
#
# This matches: set tx_start=1 before posedge at cycle -3, after posedge check.
# Then for vec 0: set tx_start=0 before posedge, after posedge check.
#
# For the reset between frames: we need to reset the DUT at vec 5210.
# But the vector file shows rst_n=1. We'll drive rst_n=0 at vec 5210 anyway
# (to reset the baud_gen), then rst_n=1 at 5213 with tx_start=1.
# The vectors at 5210-5212 will have rst_n=0 in the TB but the vector file says 1.
# The expected outputs at 5210-5212 are tx_out=1 (idle), which the reset produces.
# So the check should still pass.
#
# Actually, let me verify: what does the vector file expect at vecs 5210-5212?
for i in range(5208, 5216):
    print(f"vec {i}: in={data['vectors'][i]['inputs']} exp={data['vectors'][i]['expected']}")