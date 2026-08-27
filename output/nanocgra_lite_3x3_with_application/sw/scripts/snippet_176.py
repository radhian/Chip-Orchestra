import json, sys
sys.path.insert(0, '.')
from golden.model.top import sobel_stream
from golden.model.params import IMG_W, IMG_H, OUT_W, OUT_H

with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = g['pixels']
print("N=", g['N'], "len pixels=", len(pixels), "expected", IMG_W*IMG_H)
flat = [p for row in pixels for p in row]
out = sobel_stream(flat)
print("golden out len", len(out), "expected", OUT_W*OUT_H)
print("first 30 golden:", out[:30])
with open('context/golden_ref.json','w') as f:
    json.dump(out, f)