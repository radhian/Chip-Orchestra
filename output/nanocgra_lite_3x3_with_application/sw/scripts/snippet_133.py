import json
path = f'golden/vectors/line_buffer.json'
with open(path) as f:
    data = json.load(f)
for i in [36,37,38]:
    v = data['vectors'][i]
    print(f"vec {i}: in={v['inputs']} exp={v['expected']['row_out']}")