import json, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream

data = json.load(open('context/chip_input_grid.json'))
pixels = data['pixels']
flat = [p for row in pixels for p in row]
out = sobel_stream(flat)
print("len:", len(out), "min:", min(out), "max:", max(out))
# write golden mem
with open('rtl/sobel_golden.mem', 'w') as f:
    for v in out:
        f.write(f"{v:02x}\n")
print("wrote rtl/sobel_golden.mem")
# also verify input mem matches
inp = open('rtl/sobel_input.mem').read().split()
print("input mem len:", len(inp), "first:", inp[:5])
print("match:", all(int(inp[i],16)==flat[i] for i in range(len(flat))))