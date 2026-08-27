import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# find vectors where rx_valid=1
valid_vecs = [v for v in d['vectors'] if v['expected'].get('rx_valid')==1]
print('num valid:', len(valid_vecs))
for v in valid_vecs[:5]:
    print('in:', {k:val for k,val in v['inputs'].items() if k!='clk'}, 'exp:', v['expected'])