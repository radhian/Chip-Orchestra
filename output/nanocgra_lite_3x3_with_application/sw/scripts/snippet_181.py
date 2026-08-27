import json
with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/golden_ref.json') as f:
    gref = json.load(f)

# Let's look at the chip output pattern. The golden values are ~58-62 (small gradients, smooth image).
# Chip values are weird: 100, 132, 10, 132, 12, 134...
# Let's see if chip output relates to golden via some bit manipulation
print("chip hex first 20:", [hex(x) for x in cmem[:20]])
print("gold hex first 20:", [hex(x) for x in gref[:20]])

# 100=0x64, 68=0x44. 132=0x84, 56=0x38. 10=0x0a, 58=0x3a. 132=0x84, 60=0x3c
# 0x64 vs 0x44: bit 5 set in chip? 0x64=0110_0100, 0x44=0100_0100. diff = bit5=0x20
# 0x84 vs 0x38: 1000_0100 vs 0011_1000. very different
# 0x0a vs 0x3a: 0000_1010 vs 0011_1010. diff = bits 5,4 = 0x30
# Hmm. Let me check if chip is computing on wrong pixels (shifted window)

# Let me check: maybe the chip is computing sobel but with a 1-pixel shifted window
# Golden[0] = sobel of window at (row=2,col=2): pixels[2][2..4], pixels[3][2..4], pixels[4][2..4]
# Let me compute what window would give chip[0]=100
from golden.model.sobel_core import sobel_compute
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']

# golden[0] uses window centered at (2,2)
def win_at(r,c):
    return [px[r-1][c-1],px[r-1][c],px[r-1][c+1],px[r][c-1],px[r][c],px[r][c+1],px[r+1][c-1],px[r+1][c],px[r+1][c+1]]

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