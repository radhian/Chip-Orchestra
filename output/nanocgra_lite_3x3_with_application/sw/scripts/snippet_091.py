import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
vs = d['vectors']
# Find all rx_byte values
with_byte = [(i, vs[i]['expected'].get('rx_byte')) for i,v in enumerate(vs) if 'rx_byte' in v['expected']]
print('with_byte:', with_byte)
# The rx_in pattern: idle high, then start bit (0) for 434 cycles, then 8 data bits, then stop.
# Let's look at the rx_in around the first falling edge
# Find first 0 in rx_in
first_zero = next(i for i,v in enumerate(vs) if v['inputs']['rx_in']==0)
print('first zero at', first_zero)
# Show rx_in from first_zero for 10*434 cycles
rx = [v['inputs']['rx_in'] for v in vs]
# Find the bit pattern: sample at baud ticks (every 434 cycles starting from 433)
# tick positions: 433, 867, 1301, ...
# At tick 433 (first tick), prev_line should be 1 and rx_in=0 -> start detected
# Then ticks 867..3905 sample 8 data bits
for tick_num in range(10):
    tick_pos = 433 + tick_num * 434
    if tick_pos < len(rx):
        print(f'tick {tick_num} at pos {tick_pos}: rx_in={rx[tick_pos]}')