import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
vs = d['vectors']
# Find vectors with rx_byte in expected
with_byte = [(i, vs[i]['expected']['rx_byte']) for i,v in enumerate(vs) if 'rx_byte' in v['expected']]
print('num with rx_byte:', len(with_byte))
print('first 5:', with_byte[:5])
# Show rx_in pattern leading to first valid
p = 3905
# The start bit is detected at the first baud tick after falling edge.
# Let's find where rx_in goes from 1 to 0 before p
trans = [i for i in range(1, p) if vs[i-1]['inputs']['rx_in']==1 and vs[i]['inputs']['rx_in']==0]
print('falling edges before p:', trans[:5])
# Show rx_in from first falling edge to p
if trans:
    fe = trans[0]
    print('falling edge at', fe)
    print('rx_in from fe to p:', [vs[j]['inputs']['rx_in'] for j in range(fe, p+1)])
    # fe should be around 433 (first baud tick) - the start bit is sampled at tick 0
    print('fe/434 =', fe/434)