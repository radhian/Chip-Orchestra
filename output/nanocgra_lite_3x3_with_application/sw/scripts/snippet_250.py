import sys, json
sys.path.insert(0, 'golden')
from model.top import sobel_stream
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = [p for row in grid['pixels'] for p in row]
out = sobel_stream(pixels)
print("golden out len:", len(out))
print("first 20:", [hex(x) for x in out[:20]])
# Compare with waves/golden_output.mem
with open('waves/golden_output.mem') as f:
    gmem = [int(line.strip(),16) for line in f if line.strip() and not line.startswith('//')]
print("gmem len:", len(gmem), "first 20:", [hex(x) for x in gmem[:20]])
print("match:", out == gmem)