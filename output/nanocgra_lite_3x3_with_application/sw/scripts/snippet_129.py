import json, os

# Check the full vector lists for cgra_3x3, sobel_core, window_3x3, mmio_bus, pe, sram_32b
# to get ALL vectors (not just transitions) since they're small
for mod in ['cgra_3x3','sobel_core','window_3x3','mmio_bus','pe']:
    path = f'golden/vectors/{mod}.json'
    with open(path) as f:
        data = json.load(f)
    print(f"=== {mod}: {len(data['vectors'])} vectors ===")
    for i, v in enumerate(data['vectors']):
        print(f"  vec {i}: in={v['inputs']} exp={v['expected']}")
    print()