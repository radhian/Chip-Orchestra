import json
with open('golden/vectors/nano_cgra_3x3_sobel_accelerator_v4.json') as f:
    d = json.load(f)
v = d['vectors'][0]
print('keys:', list(v.keys()))
print('inputs keys:', list(v['inputs'].keys()))
print('expected keys:', list(v['expected'].keys()))
print('pixels len:', len(v['inputs']['pixels']))
print('sobel_out_stream len:', len(v['expected']['sobel_out_stream']))
print('first 10 expected:', v['expected']['sobel_out_stream'][:10])
print('first 10 pixels:', v['inputs']['pixels'][:10])