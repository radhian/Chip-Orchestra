import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# baud_gen: first tick at index 433 (0-indexed, so after 434 clocks).
# ticks at 433, 867, 1301, ... interval=434
# rx_valid=1 at index 3905. Is 3905 a tick? 3905 = 433 + 3472 = 433 + 8*434 = 433+3472=3905. Yes!
# So tick at 3905 = 433 + 8*434. That's the 9th tick (0-indexed: tick 8).
# Start bit falling edge: let's find which tick the start was detected at.
# The falling edge at rx_in index 3038. Which tick is at/after 3038?
# ticks: 433, 867, 1301, 1735, 2169, 2603, 3037, 3471, 3905, ...
# 3037 is a tick. At tick 3037, rx_in=? 
print('rx_in at tick 3037:', d['vectors'][3037]['inputs']['rx_in'])
print('rx_in at tick 3038:', d['vectors'][3038]['inputs']['rx_in'])
# The golden model: at each tick, check prev_line vs rx_in.
# At tick 3037: prev_line was rx_in from previous tick (2603).
print('rx_in at tick 2603:', d['vectors'][2603]['inputs']['rx_in'])
# If prev_line=1 at tick 2603, and rx_in=0 at tick 3037... but rx_in at 3037?
# Let me check around 3037
for i in range(3035, 3045):
    print(f'  [{i}] rx_in={d["vectors"][i]["inputs"]["rx_in"]}')