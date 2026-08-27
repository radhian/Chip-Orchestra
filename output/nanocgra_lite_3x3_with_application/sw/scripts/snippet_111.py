import json
with open('golden/vectors/mmio_bus.json') as f:
    d = json.load(f)
for v in d['vectors']:
    print('in:', {k:val for k,val in v['inputs'].items() if k!='clk'}, 'exp:', v['expected'])