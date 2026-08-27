import json, os, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream
from model.params import IMG_W, IMG_H, OUT_W, OUT_H

with open('context/chip_input_grid.json') as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]
out = sobel_stream(flat)

with open('waves/chip_output.mem') as f:
    lines = [l.strip() for l in f if l.strip() and not l.startswith('//')]
cmem = [int(l,16) for l in lines]

# Check: even indices match, odd indices mismatch?
for i in range(30):
    mark = "OK" if out[i]==cmem[i] else "MM"
    print(f"idx {i:2d} golden={out[i]:3d} chip={cmem[i]:3d} {mark}")