import json, os

# Get full line_buffer vectors
path = f'golden/vectors/line_buffer.json'
with open(path) as f:
    data = json.load(f)
print(f"=== line_buffer: {len(data['vectors'])} vectors ===")
for i, v in enumerate(data['vectors']):
    inp = v['inputs']
    exp = v['expected']['row_out']
    # compact: show first/last few
    print(f"  vec {i}: in(shift_en={inp['shift_en']},pixel_in={inp['pixel_in']},rst_n={inp['rst_n']}) exp_row[0..4]={exp[:5]} ... [{exp[-5:]}]")