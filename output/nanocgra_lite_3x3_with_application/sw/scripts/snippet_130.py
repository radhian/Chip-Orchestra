import json, os

# Get full cgra_3x3 and sobel_core vectors
for mod in ['cgra_3x3','sobel_core']:
    path = f'golden/vectors/{mod}.json'
    with open(path) as f:
        data = json.load(f)
    print(f"=== {mod}: {len(data['vectors'])} vectors ===")
    for i, v in enumerate(data['vectors']):
        print(f"  vec {i}: in={v['inputs']} exp={v['expected']}")
    print()