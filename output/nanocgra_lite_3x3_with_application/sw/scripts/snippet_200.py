import json, os, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream
from model.params import IMG_W, IMG_H, OUT_W, OUT_H

with open('context/chip_input_grid.json') as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]
out = sobel_stream(flat)

# Compare with chip_output.mem
with open('waves/chip_output.mem') as f:
    lines = [l.strip() for l in f if l.strip() and not l.startswith('//')]
cmem = [int(l,16) for l in lines]
print("chip mem len", len(cmem))
print("chip first 30:", cmem[:30])
print("golden first 30:", out[:30])
# show mismatches
mm = [(i, out[i], cmem[i]) for i in range(min(30,len(cmem),len(out))) if out[i]!=cmem[i]]
for m in mm: print("idx", m[0], "golden", m[1], "chip", m[2])