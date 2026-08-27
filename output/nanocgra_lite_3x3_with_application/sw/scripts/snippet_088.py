import json
# Check uart_rx vectors - find rx_valid=1 positions
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
vs = d['vectors']
print('total vectors:', len(vs))
valids = [(i, vs[i]['expected'].get('rx_byte',None)) for i,v in enumerate(vs) if v['expected'].get('rx_valid',0)==1]
print('num rx_valid=1:', len(valids))
print('first 5 valid positions:', valids[:5])
# Show the rx_in pattern around first valid
if valids:
    p = valids[0][0]
    print('rx_in around first valid (p-15..p):', [vs[j]['inputs']['rx_in'] for j in range(max(0,p-15), p+1)])
    print('rx_byte at first valid:', vs[p]['expected'].get('rx_byte'))