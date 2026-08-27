import json
import sys
sys.path.insert(0, 'golden')
from model.uart_rx import UartRx

with open('golden/vectors/uart_rx.json') as f:
    data = json.load(f)

# Find all transitions in uart_rx vectors
transitions = []
prev_valid = 0
prev_byte = 0
for i in range(len(data['vectors'])):
    exp = data['vectors'][i]['expected']
    valid = exp.get('rx_valid', 0)
    byte_val = exp.get('rx_byte', prev_byte)
    if valid != prev_valid or (valid and byte_val != prev_byte):
        transitions.append((i, valid, byte_val if valid else None))
    prev_valid = valid
    if valid:
        prev_byte = byte_val

print(f"Transitions ({len(transitions)}):")
for t in transitions:
    print(f"  vec {t[0]}: rx_valid={t[1]}, rx_byte={t[2]}")

# Check rx_in values at transition points
print("\nrx_in at transitions:")
for t in transitions:
    i = t[0]
    print(f"  vec {i}: rx_in={data['vectors'][i]['inputs']['rx_in']}, exp={data['vectors'][i]['expected']}")