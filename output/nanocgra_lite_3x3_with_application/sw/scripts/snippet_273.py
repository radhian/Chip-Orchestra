import sys
sys.path.insert(0, '.')
from golden.model.top import sobel_stream
import json

with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = [p for row in grid['pixels'] for p in row]
out = sobel_stream(pixels)

# Check how many results are produced per pixel
# The golden model produces a result when col>=2 and row>=2
# First result at pixel index = 2*32+2 = 66
# Last result at pixel index = 31*32+31 = 1023
# Total results = 30*30 = 900
# So results are produced at pixels 66..1023 (958 pixels), but only 900 produce results
# Actually results produced when col>=2 and row>=2: that's 30*30=900 results

# Let's trace which pixel indices produce results
results_indices = []
for idx in range(len(pixels)):
    row = idx // 32
    col = idx % 32
    if col >= 2 and row >= 2:
        results_indices.append(idx)
print("First result at pixel idx:", results_indices[0])
print("Last result at pixel idx:", results_indices[-1])
print("Total results:", len(results_indices))
print("Results per row: 30, rows with results: 30")