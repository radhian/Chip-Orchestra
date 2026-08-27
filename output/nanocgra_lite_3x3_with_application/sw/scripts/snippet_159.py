import json
# The uart_rx vectors show rx_valid=1 at vecs 3905, 8246, 12587, 16928
# and rx_byte at vecs 4340, 13022, 17363 (from earlier analysis).
# Let me find where rx_byte appears (non-default).
with open('golden/vectors/uart_rx.json') as f:
    data = json.load(f)

byte_vecs = []
for i, v in enumerate(data['vectors']):
    exp = v['expected']
    if 'rx_byte' in exp:
        byte_vecs.append((i, exp['rx_byte'], exp.get('rx_valid', 0), v['inputs']['rx_in']))
print(f"Vectors with rx_byte: {len(byte_vecs)}")
for b in byte_vecs:
    print(f"  vec {b[0]}: rx_byte={b[1]}, rx_valid={b[2]}, rx_in={b[3]}")