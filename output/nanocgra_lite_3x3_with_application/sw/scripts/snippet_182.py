import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/golden_ref.json') as f:
    gref = json.load(f)
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']

def win_at(r,c):
    return [px[r-1][c-1],px[r-1][c],px[r-1][c+1],px[r][c-1],px[r][c],px[r][c+1],px[r+1][c-1],px[r+1][c],px[r+1][c+1]]

# golden[0] uses window centered at (2,2)
w = win_at(2,2)
print("win(2,2):", w, "golden:", sobel_compute(w))

# Try shifted windows to find chip[0]=100
for dr in range(-2,3):
    for dc in range(-2,3):
        r,c = 2+dr, 2+dc
        if r<1 or c<1 or r>30 or c>30: continue
        w = win_at(r,c)
        gx,gy,out = sobel_compute(w)
        if out == cmem[0]:
            print(f"chip[0]={cmem[0]} matches window at ({r},{c})")

# Also check chip[1]=132
for dr in range(-2,3):
    for dc in range(-2,3):
        r,c = 2+dr, 3+dc
        if r<1 or c<1 or r>30 or c>30: continue
        w = win_at(r,c)
        gx,gy,out = sobel_compute(w)
        if out == cmem[1]:
            print(f"chip[1]={cmem[1]} matches window at ({r},{c})")