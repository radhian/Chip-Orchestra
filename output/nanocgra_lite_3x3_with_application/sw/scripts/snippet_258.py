import sys, json
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
px = grid['pixels']
pixels = [p for row in px for p in row]

with open('waves/chip_output.mem') as f:
    clines = f.readlines()
cvals = [int(l.strip(),16) for l in clines if l.strip() and not l.startswith('//')]

# Hypothesis: the controller drops every other pixel during TX.
# When it drops a pixel, pixel_cnt doesn't increment, so the next accepted
# pixel gets the wrong col/row. This causes the line buffers and window
# to be misaligned.
#
# Let me simulate this: the controller accepts a pixel, produces a result,
# then DROPS the next pixel (because it's in S_TX_RESULT/S_NEXT), then
# accepts the one after that, etc.
#
# So the controller processes pixels: 0,1,2,...,66 (first 2 rows + first 2 cols)
# without producing results (no TX, so no dropping).
# Then at pixel 66 (row=2, col=2), it produces result and drops pixel 67.
# Then at pixel 68 (row=2, col=4 in the original stream, but pixel_cnt=67
# so col=3), it produces result and drops pixel 69.
# etc.
#
# So the controller's pixel_cnt is always 1 behind the actual pixel stream
# after the first result. The window is computed with the wrong col_cnt
# (off by 1), causing the line buffer to read/write at the wrong column.

# Let me simulate this scenario:
# - Process pixels normally until first result (row=2, col=2)
# - After each result, skip the next pixel (dropped)
# - The line buffers use the controller's col_cnt (which is off by 1)

IMG_W = 32
lb_rn2 = [0] * IMG_W
lb_rn1 = [0] * IMG_W
wcols = [[0, 0, 0] for _ in range(3)]
results = []

# Simulate the controller's behavior with pixel dropping
pixel_cnt = 0  # controller's pixel counter
drop_next = False
for stream_idx, pxx in enumerate(pixels):
    if drop_next:
        drop_next = False
        continue  # pixel dropped, pixel_cnt unchanged
    
    row = pixel_cnt // IMG_W
    col = pixel_cnt % IMG_W
    pxx = int(pxx) & 0xFF
    
    rn2 = lb_rn2[col] if row >= 2 else 0
    rn1 = lb_rn1[col] if row >= 1 else 0
    
    for r in range(3):
        wcols[r] = wcols[r][1:] + [0]
    wcols[0][2] = rn2
    wcols[1][2] = rn1
    wcols[2][2] = pxx
    
    if row >= 1:
        lb_rn2[col] = lb_rn1[col]
    lb_rn1[col] = pxx
    
    if col >= 2 and row >= 2:
        w = [wcols[r][c] for r in range(3) for c in range(3)]
        out = sobel_compute(w)[2]
        results.append(out)
        drop_next = True  # drop next pixel during TX
    
    pixel_cnt += 1

print("With pixel dropping after each result:")
print("results count:", len(results))
print("first 20:", [hex(x) for x in results[:20]])
print("chip     :", [hex(x) for x in cvals[:20]])
print("match:", results[:20] == cvals[:20])