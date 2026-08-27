import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# Find the transition from 1->0 (start bit falling edge) before index 3905
prev = 1
transitions = []
for i in range(max(0,3905-4340*2), 3905+5):
    v = d['vectors'][i]
    cur = v['inputs']['rx_in']
    if prev == 1 and cur == 0:
        transitions.append(i)
    prev = cur
print('falling edges (1->0):', transitions)
# Show the bit pattern: sample at baud intervals from start
if transitions:
    start_idx = transitions[0]
    print(f'start bit at index {start_idx}')
    # baud_div=434. Sample at start_idx + 434*k for k=0..9
    for k in range(11):
        si = start_idx + 434*k
        if si < len(d['vectors']):
            print(f'  sample[{k}] idx={si} rx_in={d["vectors"][si]["inputs"]["rx_in"]} exp_valid={d["vectors"][si]["expected"].get("rx_valid","?")}')