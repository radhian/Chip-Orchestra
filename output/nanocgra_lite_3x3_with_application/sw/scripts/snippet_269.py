import json, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream

with open('context/chip_input_grid.json') as f:
    grid = json.load(f)

# Flatten the 2D pixels
pixels_2d = grid['pixels']
flat = [p for row in pixels_2d for p in row]
print("Total pixels:", len(flat))

results = sobel_stream(flat)
print("Total results:", len(results))
print("First 10:", results[:10])

# Compare with waves/golden_output.mem
with open('waves/golden_output.mem') as f:
    golden_mem = [int(line.strip(), 16) for line in f if line.strip()]
print("Golden mem count:", len(golden_mem))
print("Golden mem first 10:", golden_mem[:10])
print("Match:", results == golden_mem)