import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']

def win_at(r,c):
    return [px[r-1][c-1],px[r-1][c],px[r-1][c+1],px[r][c-1],px[r][c],px[r][c+1],px[r+1][c-1],px[r+1][c],px[r+1][c+1]]

# Search wider for chip[0]=100
print("Searching for chip[0]=100...")
for r in range(1,31):
    for c in range(1,31):
        w = win_at(r,c)
        gx,gy,out = sobel_compute(w)
        if out == cmem[0]:
            print(f"  chip[0]={cmem[0]} matches window at ({r},{c})")

print("Searching for chip[1]=132...")
for r in range(1,31):
    for c in range(1,31):
        w = win_at(r,c)
        gx,gy,out = sobel_compute(w)
        if out == cmem[1]:
            print(f"  chip[1]={cmem[1]} matches window at ({r},{c})")

# Maybe the chip is computing on a different window arrangement (wrong pixel order)
# Let's try: what if the window has rows swapped, or uses wrong line buffer data
# Let me just compute sobel on various permutations of win(2,2)
w = win_at(2,2)
print("win(2,2):", w)
import itertools
# Try all permutations? too many. Try specific: reversed rows, transposed, etc.
# Maybe the line buffer tap is wrong - getting wrong column
# Let's check: what sobel values come from windows at row 2, various cols
for c in range(1,8):
    w = win_at(2,c)
    gx,gy,out = sobel_compute(w)
    print(f"  win(2,{c}): out={out}")