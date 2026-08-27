import json
# Load canonical input
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = g['pixels']
print("N", g['N'])
print("len", len(pixels), "row0", pixels[0][:8])

# Run golden sobel_stream
import sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream
out = sobel_stream([p for row in pixels for p in row])
print("out len", len(out))
print("first 12 golden:", [hex(x) for x in out[:12]])