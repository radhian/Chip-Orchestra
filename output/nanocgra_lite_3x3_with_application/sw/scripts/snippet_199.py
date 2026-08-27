import json, os, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream
from model.params import IMG_W, IMG_H, OUT_W, OUT_H

with open('context/chip_input_grid.json') as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]
out = sobel_stream(flat)
print("len", len(out))
print("first 30:", out[:30])
# Compare with golden_output.mem
with open('waves/golden_output.mem') as f:
    gmem = [int(line.strip(),16) for line in f if line.strip()]
print("golden mem first 30:", gmem[:30])
print("match:", out == gmem)