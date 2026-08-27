import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# The falling edge at 3038. Let's check: baud_div=434
# start bit detected at 3038 (falling edge). Then sample 8 data bits at 3038+434, +868, ...
start_idx = 3038
print(f'start bit falling edge at index {start_idx}')
for k in range(11):
    si = start_idx + 434*k
    if si < len(d['vectors']):
        print(f'  +{k} idx={si} rx_in={d["vectors"][si]["inputs"]["rx_in"]} exp={d["vectors"][si]["expected"]}')