import json
import sys
sys.path.insert(0, 'golden')
from model.uart_rx import UartRx

with open('golden/vectors/uart_rx.json') as f:
    data = json.load(f)

# Only 6 mismatches! The rx_valid mismatches are off by 1-2 cycles.
# The rx_byte=165 at vec 4340 matches (model also has 165 at 4340).
# Let me look at the mismatches more carefully.

rx = UartRx()
rx.reset()
for i in range(len(data['vectors'])):
    inp = data['vectors'][i]['inputs']
    exp = data['vectors'][i]['expected']
    byte_val, valid = rx.step(inp['clk'], inp['rst_n'], inp['rx_in'])
    exp_valid = exp.get('rx_valid', None)
    if exp_valid is not None and valid != exp_valid:
        # Check surrounding vectors
        print(f"vec {i}: valid MISMATCH model={valid} exp={exp_valid} rx_in={inp['rx_in']}")
        if i > 0:
            prev = data['vectors'][i-1]['expected']
            print(f"  prev vec {i-1}: exp={prev}")
        if i < len(data['vectors'])-1:
            nxt = data['vectors'][i+1]['expected']
            print(f"  next vec {i+1}: exp={nxt}")