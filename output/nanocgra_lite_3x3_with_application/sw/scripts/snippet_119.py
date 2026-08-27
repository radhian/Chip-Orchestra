import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# rx_byte=165=0xA5=10100101 at index 4340. rx_valid=1 at 3905.
# Let's look at 3905 and 4340 more carefully
for i in [3905, 3906, 4340]:
    print(f'  [{i}] rx_in={d["vectors"][i]["inputs"]["rx_in"]} exp={d["vectors"][i]["expected"]}')
# 165 = 10100101. LSB first: 1,0,1,0,0,1,0,1
# The data bits sampled at baud ticks after start:
# start at 3038 (falling edge detected). 
# Golden model: on tick where prev=1 and rx_in=0, go to DATA, bit_idx=0
# Next tick (3038+434=3472): sample bit0 = rx_in=1
# Next tick (3472+434=3906): sample bit1 = rx_in=1 ... wait
# Actually the golden samples at the NEXT tick after detecting start
# Let me check: at 3038 tick, prev_line=1, rx_in=0 -> go to DATA, bit_idx=0, shreg=0
# at 3472 tick: state=DATA, sample rx_in=1 -> shreg[0]=1, bit_idx=1
# at 3906 tick: state=DATA, sample rx_in=1 -> shreg[1]=1, bit_idx=2
# ... but rx_valid=1 at 3905, not 3906. Hmm.
# Wait, the golden model step function: tick = bg.step(). If tick, do state machine.
# The vector at index i represents the state AFTER processing cycle i.
# So at index 3905, the bg tick happened and rx_valid was set.
# Let me check: 3038 + 434*9 = 3038 + 3906 = 6944. That's 9 ticks after start.
# But rx_valid at 3905 = 3038+868+1? No.
# Actually 3905 = 3038 + 867. 867 = 2*434 - 1. Hmm.
# Let me reconsider: maybe the falling edge is at a different index.
# Let me check when rx_valid=1: index 3905. 
# 3905 = 3038 + 867. 867/434 = 2.0. So 2 baud ticks after start.
# That means only 2 data bits? No, that can't be right for 8 bits.
# Let me look at the actual rx_in values from 3038 to 3910
print('\nrx_in from 3038 to 3910 (every 434):')
for k in range(0, 3):
    si = 3038 + 434*k
    print(f'  idx={si} rx_in={d["vectors"][si]["inputs"]["rx_in"]}')
# Actually maybe the baud_gen in the test has a different divider.
# Let me check: 3905-3038 = 867. If baud_div were 289, then 3 ticks = 867. 
# 867/3 = 289. Hmm, 50e6/115200 = 434. But maybe the test uses a different clk?
# Actually wait - the test might use a smaller baud_div for simulation speed.
# Let me check the baud_gen vectors
with open('golden/vectors/baud_gen.json') as f:
    bd = json.load(f)
ticks = [i for i,v in enumerate(bd['vectors']) if v['expected'].get('baud_tick')==1]
print('\nbaud_gen tick indices (first 15):', ticks[:15])
print('intervals:', [ticks[i+1]-ticks[i] for i in range(min(14,len(ticks)-1))])