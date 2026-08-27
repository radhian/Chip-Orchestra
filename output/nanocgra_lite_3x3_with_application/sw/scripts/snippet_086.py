import json
with open('golden/vectors/nano_cgra_3x3_sobel_accelerator_v4.json') as f:
    d = json.load(f)
v = d['vectors'][0]
print('keys in vector:', list(v.keys()))
print('keys in inputs:', list(v['inputs'].keys()))
print('keys in expected:', list(v['expected'].keys()))
print('len pixels:', len(v['inputs']['pixels']))
print('len sobel_out_stream:', len(v['expected']['sobel_out_stream']))
print('first 10 expected:', v['expected']['sobel_out_stream'][:10])
# compare with sobel_golden.mem
with open('rtl/sobel_golden.mem') as f:
    gm = [int(x.strip(),16) for x in f if x.strip()]
print('len golden mem:', len(gm))
print('first 10 golden mem:', gm[:10])
print('match expected vs golden mem:', v['expected']['sobel_out_stream'] == gm)
# compare input pixels with sobel_input.mem
with open('rtl/sobel_input.mem') as f:
    im = [int(x.strip(),16) for x in f if x.strip()]
print('len input mem:', len(im))
print('first 10 input mem:', im[:10])
print('match input pixels vs input mem:', v['inputs']['pixels'] == im)