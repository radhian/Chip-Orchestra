import sys
sys.path.insert(0, '.')
from golden.model.top import sobel_stream
import json

with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = [p for row in grid['pixels'] for p in row]
out = sobel_stream(pixels)
print("golden out first 20:", [hex(x) for x in out[:20]])
print("golden out len:", len(out))

# Compare with waves/golden_output.mem
with open('waves/golden_output.mem') as f:
    mem = [int(line.strip(),16) for line in f if line.strip()]
print("golden_output.mem first 20:", [hex(x) for x in mem[:20]])
print("golden_output.mem len:", len(mem))
print("MATCH:", out==mem)
if out!=mem:
    for i in range(len(out)):
        if out[i]!=mem[i]:
            print(f"  diff at {i}: golden={hex(out[i])} mem={hex(mem[i])}")
            if i>5: break