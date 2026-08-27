import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# Ticks at: 433, 867, 1301, 1735, 2169, 2603, 3037, 3471, 3905, 4339, ...
# At tick 3037: rx_in=1, prev_line (from tick 2603) = 0. So no falling edge (0->1, not 1->0).
# Wait, prev_line is updated to rx_in at each tick. So:
# tick 2603: rx_in=0, prev_line becomes 0
# tick 3037: rx_in=1, prev_line was 0 -> no falling edge (it's 0->1). prev_line becomes 1
# tick 3471: rx_in=? 
print('rx_in at tick 3471:', d['vectors'][3471]['inputs']['rx_in'])
# tick 3471: rx_in=0, prev_line was 1 (from tick 3037) -> FALLING EDGE! Start bit detected.
# Then DATA state, bit_idx=0
# tick 3905: sample bit0. rx_in=1. 
# But rx_valid=1 at 3905! That means after sampling bit0, bit_idx becomes 1, not 8.
# Unless... the golden model detects start and samples bit0 on the SAME tick?
# Let me re-read the golden model:
# STOP state: if prev_line==1 and rx_in==0: state=DATA, bit_idx=0, shreg=0
# DATA state: shreg |= rx_in << bit_idx; bit_idx+=1; if bit_idx==8: rx_byte=shreg, state=STOP, rx_valid=1
# So at tick 3471: STOP->DATA (start detected), bit_idx=0
# At tick 3905: DATA, sample rx_in=1 -> shreg[0]=1, bit_idx=1. NOT valid yet.
# But the vector says rx_valid=1 at 3905! 
# Wait, maybe I'm wrong about when the falling edge happens.
# Let me check: maybe the test applies inputs differently.
# The vector index = clock cycle. The golden model step is called per cycle.
# At each cycle: tick = bg.step(). If tick, process FSM.
# So the bg tick happens at cycles 433, 867, ...
# But the vector expected output is the state AFTER that cycle's step.
# So at cycle 3905, bg tick happens, FSM processes, and rx_valid=1.
# For rx_valid=1 at cycle 3905 (tick 8), we need bit_idx to reach 8 at this tick.
# That means start was detected at tick 3471 (tick 7), and then... 
# Wait, tick 3471 is tick 7 (0-indexed: 433=0, 867=1, ..., 3471=7, 3905=8)
# If start detected at tick 7 (3471), then:
# tick 8 (3905): DATA, sample bit0. bit_idx=1. Not valid.
# This doesn't work. Unless start is detected earlier.
# Let me check tick 6 (3037): rx_in=1, prev_line from tick 5 (2603)=0. No falling edge.
# tick 5 (2603): rx_in=0, prev_line from tick 4 (2169)=?
print('rx_in at tick 2169:', d['vectors'][2169]['inputs']['rx_in'])
print('rx_in at tick 1735:', d['vectors'][1735]['inputs']['rx_in'])
print('rx_in at tick 1301:', d['vectors'][1301]['inputs']['rx_in'])
print('rx_in at tick 867:', d['vectors'][867]['inputs']['rx_in'])
print('rx_in at tick 433:', d['vectors'][433]['inputs']['rx_in'])