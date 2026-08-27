import json
# Now let me understand the uart_tx vector timing. There are 8684 mismatches.
# The uart_tx vectors have tx_start=0, data_in=0 for ALL vectors, yet the expected
# tx_out changes over time. This means the vectors were generated with a tx_start pulse
# at some point, but the vector file only records tx_start=0.
# Let me look at the first few hundred vectors to find where tx_start might be 1.
import sys
sys.path.insert(0, 'golden')

with open('golden/vectors/uart_tx.json') as f:
    data = json.load(f)

# Find any vector where tx_start != 0 or data_in != 0
nonzero = []
for i, v in enumerate(data['vectors']):
    inp = v['inputs']
    if inp.get('tx_start', 0) != 0 or inp.get('data_in', 0) != 0:
        nonzero.append((i, inp, v['expected']))
print(f"Vectors with tx_start!=0 or data_in!=0: {len(nonzero)}")
for n in nonzero[:20]:
    print(n)