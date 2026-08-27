# Let's compute the golden Sobel for the first few windows manually and see what the chip is producing for odd indices.
import sys, json
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
px = grid['pixels']

# Golden streaming: result index k corresponds to window at (row=2+kr, col=2+kc) where k = kr*30+kc
# Let's compute the first few windows and results
def window_at(px, r, c):
    return [px[r+dr][c+dc] for dr in range(3) for dc in range(3)]

for k in range(6):
    kr = k // 30
    kc = k % 30
    r = 2 + kr
    c = 2 + kc
    w = window_at(px, r, c)
    gx, gy, out = sobel_compute(w)
    print(f"k={k} (r={r},c={c}) win={w} gx={gx} gy={gy} out={hex(out)}")

# Now what does the chip produce? chip[0]=0x44 (matches k=0), chip[1]=0x9c
# 0x9c = 156. Let's see what window would give 156.
# Let's check: is the chip computing on a shifted window for odd indices?
# Maybe the chip is emitting results for windows that are offset by one column.

# Let's compute golden for k=1 (r=2, c=3)
w = window_at(px, 2, 3)
print("k=1 golden win:", w, "out:", hex(sobel_compute(w)[2]))

# What window gives 0x9c = 156?
# Let's brute force: search all 3x3 windows in the image for out=156
for r in range(30):
    for c in range(30):
        w = window_at(px, r, c)
        out = sobel_compute(w)[2]
        if out == 0x9c:
            print(f"out=0x9c at r={r} c={c}")
            if r < 5 and c < 10:
                pass