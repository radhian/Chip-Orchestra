import json
# Read the canonical input
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
print("N:", grid['N'])
print("pixels count:", len(grid['pixels']))
print("first row:", grid['pixels'][0][:10])