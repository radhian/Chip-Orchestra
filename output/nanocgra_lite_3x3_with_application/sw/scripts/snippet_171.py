import json, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream

with open('context/chip_input_grid.json') as f:
    grid = json.load(f)

pixels = grid['pixels']
flat = [p for row in pixels for p in row]
print("N=", grid['N'], "flat len=", len(flat))

out = sobel_stream(flat)
print("out len=", len(out))
print("first 30:", out[:30])

# write golden output
with open('waves/golden_output.mem','w') as f:
    for v in out:
        f.write("%02x\n" % v)
print("wrote waves/golden_output.mem")