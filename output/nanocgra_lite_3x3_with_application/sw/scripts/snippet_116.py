import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# Show rx_in pattern around first valid (index 3905), going back to find start bit
# baud_div=434, so 10 bits = 4340 cycles. start at 3905-4340 = -435
for i in range(0, 20):
    v = d['vectors'][i]
    print(f'  [{i}] rx_in={v["inputs"]["rx_in"]} exp={v["expected"]}')
print('...')
# find where rx_in first goes 0 before 3905
for i in range(3905-4340, 3905+5):
    if i < 0: continue
    v = d['vectors'][i]
    if v['inputs']['rx_in'] == 0:
        print(f'  [{i}] rx_in=0 (start bit region)')