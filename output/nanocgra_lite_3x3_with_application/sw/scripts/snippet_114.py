import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# find indices of valid vectors
valid_idx = [i for i,v in enumerate(d['vectors']) if v['expected'].get('rx_valid')==1]
print('valid indices:', valid_idx)
# show context around first valid
for vi in valid_idx:
    print(f'\n=== around index {vi} ===')
    for i in range(max(0,vi-12), vi+2):
        v = d['vectors'][i]
        print(f'  [{i}] rx_in={v["inputs"]["rx_in"]} exp={v["expected"]}')