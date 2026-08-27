import json
with open('golden/vectors/nano_cgra_3x3_sobel_accelerator_v4.json') as f:
    d = json.load(f)
v = d['vectors'][0]
exp = v['expected']['sobel_out_stream']
# Compare with sobel_golden.mem
with open('rtl/sobel_golden.mem') as f:
    golden_mem = [int(x.strip(),16) for x in f if x.strip()]
print('golden_mem len:', len(golden_mem))
print('golden_mem first 10:', golden_mem[:10])
print('expected first 10:', exp[:10])
print('match:', golden_mem == exp)
# Compare pixels with sobel_input.mem
with open('rtl/sobel_input.mem') as f:
    input_mem = [int(x.strip(),16) for x in f if x.strip()]
print('input_mem len:', len(input_mem))
print('input_mem first 10:', input_mem[:10])
print('pixels first 10:', v['inputs']['pixels'][:10])
print('input match:', input_mem == v['inputs']['pixels'])