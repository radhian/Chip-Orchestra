import json, os

# Get full sram_32b vectors
path = f'golden/vectors/sram_32b.json'
with open(path) as f:
    data = json.load(f)
print(f"=== sram_32b: {len(data['vectors'])} vectors ===")
for i, v in enumerate(data['vectors']):
    print(f"  vec {i}: in={v['inputs']} exp={v['expected']}")