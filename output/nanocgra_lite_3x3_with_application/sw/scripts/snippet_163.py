import json
import sys
sys.path.insert(0, 'golden')
from model.uart_rx import UartRx

with open('golden/vectors/uart_rx.json') as f:
    data = json.load(f)

# rx_in changes at: 0(0), 434(1), 868(0), 1302(1), 1736(0), 2604(1), 3038(0), 3472(1), 4341(0), ...
# These are at 434*k + offset. 0, 434, 868, 1302, 1736 = 0, 434, 868, 1302, 1736.
# 434-0=434, 868-434=434, 1302-868=434, 1736-1302=434. All 434 apart.
# But 2604-1736=868=2*434. And 3038-2604=434, 3472-3038=434.
# 
# So the rx_in pattern is: 0, 1, 0, 1, 0, (skip 2), 1, 0, 1, ...
# This is the UART frame: start(0), bit0(1), bit1(0), bit2(1), bit3(0), 
# bit4(1), bit5(0), bit6(1), stop(1).
# 
# Wait, the changes are at 0, 434, 868, 1302, 1736, 2604, 3038, 3472.
# Gaps: 434, 434, 434, 434, 868, 434, 434.
# The 868 gap means two consecutive same bits.
# 
# Frame 1: start at 0(0), bit0 at 434(1), bit1 at 868(0), bit2 at 1302(1), 
# bit3 at 1736(0), bit4 at 2170(0, no change), bit5 at 2604(1), bit6 at 3038(0), 
# bit7 at 3472(1), stop at 3906(1, no change from 3472).
# 
# Byte = bit0*1 + bit1*2 + bit2*4 + bit3*8 + bit4*16 + bit5*32 + bit6*64 + bit7*128
# = 1 + 0 + 4 + 0 + 0 + 32 + 0 + 128 = 165 = 0xA5. Match!
# 
# The rx_in changes at 434*k. This means the baud period is 434 and the first
# bit starts at vec 0. But the golden model's first tick is at 433 (with 0 warmup).
# 
# The rx_in changes at 0, 434, 868, ... = 434*k.
# The baud ticks (0 warmup) at 433, 867, 1301, ... = 433+434*k.
# So rx_in changes 1 cycle BEFORE each tick. The receiver samples at the tick,
# getting the rx_in value that was set 1 cycle earlier.
# 
# At tick 433: rx_in was set to 1 at vec 434. But 434 > 433. So at tick 433,
# rx_in is still 0 (set at vec 0). The start bit is detected at tick 433 (rx_in=0).
# At tick 867: rx_in was set to 1 at vec 434. 434 < 867. So rx_in=1 at tick 867. bit0=1.
# At tick 1301: rx_in was set to 0 at vec 868. 868 < 1301. So rx_in=0. bit1=0.
# At tick 1735: rx_in was set to 1 at vec 1302. 1302 < 1735. So rx_in=1. bit2=1.
# At tick 2169: rx_in was set to 0 at vec 1736. 1736 < 2169. So rx_in=0. bit3=0.
# At tick 2603: rx_in was set to 0 at vec 1736 (still 0). bit4=0.
# At tick 3037: rx_in was set to 1 at vec 2604. 2604 < 3037. So rx_in=1. bit5=1.
# At tick 3471: rx_in was set to 0 at vec 3038. 3038 < 3471. So rx_in=0. bit6=0.
# At tick 3905: rx_in was set to 1 at vec 3472. 3472 < 3905. So rx_in=1. bit7=1.
# rx_valid=1 at tick 3905. byte=165. Match!
# 
# So the vector generation drives rx_in at 434*k and the golden model samples
# at 433+434*k. The 1-cycle offset is because rx_in changes 1 cycle after the tick.
# 
# Now for frame 2: rx_in changes at 4341(0), 8247(1), 8682(0), 9116(1).
# 4341 = 434*10 + 1. 8247 = 434*19 + 1. 
# Frame 2 start at 4341. But the baud tick for start detection...
# If the model was NOT reset, ticks continue at 433+434*k.
# The tick just before 4341 is at 433+434*9=4339. 4339 < 4341.
# Next tick at 433+434*10=4773. 
# At tick 4773: rx_in was set to 0 at 4341. 4341 < 4773. So rx_in=0. Start bit detected.
# Then data bits at 5207, 5641, 6075, 6509, 6943, 7377, 7811, 8245.
# rx_valid at 8245. But vector shows 8246. Off by 1.
# 
# The off-by-1 suggests the vector generation used the RTL's registered baud_gen
# (1-cycle delay). With RTL timing, ticks at 434+434*k.
# Tick 434: start. Data at 868, 1302, ..., 3906. rx_valid at 3906. But vector shows 3905.
# Off by 1 in the other direction.
# 
# I think the vector generation might have used a mix of golden model and RTL timing.
# The 6 mismatches are small (off by 1-3 cycles) and only affect rx_valid timing.
# 
# For the TB: the most important checks are rx_byte (the received data), which matches
# perfectly. The rx_valid timing has minor off-by-1 issues that are likely due to
# the registered vs combinational baud_gen difference.
# 
# For the TB, I'll check rx_byte when it appears in the expected, and rx_valid
# with a tolerance of checking at the expected cycle. If the RTL produces rx_valid
# 1 cycle off, the TB will catch it as a mismatch (which is correct — it shows
# a timing difference between the RTL and the golden vectors).
# 
# Actually, the RTL uart_rx uses a registered baud_gen internally. So the RTL's
# rx_valid timing will match the vector file (which was likely generated from
# RTL simulation). Let me verify by checking the RTL timing.
# 
# The RTL baud_gen: tick=1 at posedge when cnt=433. This is registered.
# The RTL uart_rx: on posedge, if baud_tick (from baud_gen), sample.
# But baud_tick is combinational output of baud_gen (it's a reg, set on posedge).
# So uart_rx sees baud_tick=1 on the posedge AFTER baud_gen sets it.
# 
# Wait, both baud_gen and uart_rx are clocked by the same clk. In Verilog:
# baud_gen sets baud_tick<=1 on posedge at cycle 433.
# uart_rx sees baud_tick=1 on posedge at cycle 434 (because baud_tick was set
# at the posedge of cycle 433, and uart_rx reads it at the next posedge).
# 
# Actually, in simulation, both always blocks trigger on the same posedge.
# The baud_gen's non-blocking assignment sets baud_tick=1 at the END of cycle 433.
# The uart_rx's always block reads baud_tick at the BEGINNING of cycle 433 (old value).
# So uart_rx sees baud_tick=1 at cycle 434's posedge (start of cycle 434).
# 
# This means the RTL has a 1-cycle delay compared to the golden model.
# The golden model: tick and sample in the same step.
# The RTL: tick set at cycle N, sampled at cycle N+1.
# 
# So the RTL's rx_valid will be 1 cycle LATER than the golden model.
# Vector at 3905 (golden) -> RTL at 3906. But the vector shows 3905.
# 
# Hmm, but the vector at 3905 matches the golden model (0 warmup, tick at 3905).
# If the vector was generated from the golden model, the RTL will be off by 1.
# If the vector was generated from the RTL, the golden model will be off by 1.
# 
# The 6 mismatches suggest the vector was generated from the golden model with
# some reset/restart between frames that the golden model doesn't replicate exactly.
# 
# For the TB: I'll drive the rx_in as specified in the vectors and check outputs.
# The RTL will produce results that may be off by 1 cycle on rx_valid.
# This is a real timing difference that the TB should catch.
# 
# But actually, for a self-checking TB, we want to verify the RTL against the
# golden vectors. If the RTL is off by 1 cycle, that's a bug the TB catches.
# 
# Let me just write the TB to drive the exact rx_in from the vectors and check
# rx_valid and rx_byte at each cycle. The 6 mismatches will be caught as failures.
# That's correct behavior.

# Let me verify: does the RTL uart_rx produce rx_valid at 3905 or 3906?
# The RTL has baud_gen (registered) inside. The first tick is at cycle 433 (registered).
# uart_rx sees tick at cycle 434. Start detected at 434.
# Data at 868, 1302, ..., 3906. rx_valid at 3906.
# But the vector expects 3905. So the RTL will be off by 1.
# 
# UNLESS the RTL's baud_gen and uart_rx are in the same always block sensitivity.
# In Verilog, non-blocking assignments: baud_gen sets baud_tick at end of cycle 433.
# uart_rx reads baud_tick at beginning of cycle 434. So yes, 1-cycle delay.
# 
# But wait, the uart_rx.v has:
#   always @(posedge clk or negedge rst_n) begin
#     ...
#     if (baud_tick) begin
#       ...
#     end
#   end
# And baud_gen.v has:
#   always @(posedge clk or negedge rst_n) begin
#     ...
#     baud_tick <= 1'b1;
#   end
# 
# Both trigger on posedge clk. The baud_gen sets baud_tick via NBA (at end of timestep).
# The uart_rx reads baud_tick (the old value, before NBA updates).
# So uart_rx sees the NEW baud_tick value on the NEXT posedge.
# 
# This means the RTL has a 1-cycle pipeline delay. The first tick is at cycle 433
# (baud_gen), but uart_rx sees it at cycle 434.
# 
# So the RTL's rx_valid will be at 3906, not 3905. The vector expects 3905.
# The TB will catch this as a mismatch.
# 
# This is a REAL timing issue in the RTL. The TB should catch it.
# But the instructions say the TB should check against the golden vectors.
# If the RTL doesn't match, the TB fails — which is the correct behavior
# (it identifies a bug).
# 
# For the TB: I'll drive the exact stimulus from the vectors and check.
# The TB will fail on the 6 rx_valid mismatches, which is correct.
# 
# Actually, wait. Let me re-read the instructions: "Each write result compiles
# the tb WITH its DUT — if it reports errors, fix and rewrite until clean."
# This means the TB must COMPILE clean, not necessarily PASS. A TB that compiles
# but fails at runtime (due to RTL bugs) is still a valid TB.
# 
# So I should write the TB to check against the golden vectors exactly.
# If the RTL fails, that's for the repair stage to fix.

print("Approach: drive exact stimulus from vectors, check against expected. RTL timing differences will be caught as failures.")