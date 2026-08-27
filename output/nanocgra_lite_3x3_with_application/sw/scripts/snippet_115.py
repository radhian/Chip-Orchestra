import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# Show rx_in pattern around first valid (index 3905), going back further to find start bit
for i in range(3890, 3910):
    v = d['vectors'][i]
    print(f'  [{i}] rx_in={v["inputs"]["rx_in"]} exp={v["expected"]}')