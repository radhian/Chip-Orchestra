import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]
IMG_W = 32

# OK so the golden model for out[1] (idx=67, row=2, col=3):
# wcols[2] = [169, 169, 169] (row N = row 2, cols 1,2,3)
# But pixels[65]=169, pixels[66]=169, pixels[67]=169
# So wcols[2] = [pixels[65], pixels[66], pixels[67]] = [169, 169, 169] ✓
#
# Earlier I said pixels[65]=167 but that was wrong. Let me recheck.
print("pixels[64..67]:", pixels[64:68])
# pixels[64]=167, pixels[65]=169, pixels[66]=169, pixels[67]=169
# So wcols[2] at idx=67 = [pixels[65], pixels[66], pixels[67]] = [169, 169, 169] ✓
#
# Now in the RTL, sr2_1 at col=3 should be pixels[65]=169, sr2_2=pixels[66]=169, pixel_in=pixels[67]=169
# So the RTL window row N = [169, 169, 169] ✓
#
# But the chip gives 0x9c=156 for out[1]. Let me compute what window gives 156.
# 156 = |gx| + |gy|. Let me search more broadly.

def sobel_compute(win):
    w = [int(x) & 0xFF for x in win]
    gx = (-w[0] + w[2] - 2*w[3] + 2*w[5] - w[6] + w[8])
    gy = (-w[0] - 2*w[1] - w[2] + w[6] + 2*w[7] + w[8])
    mag = abs(gx) + abs(gy)
    out = max(0, min(255, mag))
    return gx, gy, out

# Search all 3x3 windows in the image for output=156
target = 156
found = []
for r in range(30):
    for c in range(30):
        win = [pixels[(r+i//3)*IMG_W + c + i%3] for i in range(9)]
        _,_,o = sobel_compute(win)
        if o == target:
            found.append((r,c,win))
print(f"Windows giving 156: {found[:10]}")

# Also check: what if the chip is using the wrong row for the line buffers?
# Maybe lb_rn2 and lb_rn1 are swapped, or the line buffer update is off by one row.
# Let me check what happens if rn2 and rn1 are swapped.
# out[1] golden: win=[155,155,155, 167,167,167, 169,169,169] -> 0x38
# If we swap rn2 and rn1: win=[167,167,167, 155,155,155, 169,169,169]
win_swap = [167,167,167, 155,155,155, 169,169,169]
print("swapped rn2/rn1:", hex(sobel_compute(win_swap)[2]))

# What if the line buffer update is delayed by one? i.e., lb_rn2 gets the value
# from two rows ago instead of one row ago?
# Or what if the line buffer read is using the POST-update value instead of pre-update?

# Let me check: what if lb_rn1 reads the NEW value (just written) instead of the old?
# At row=2, col=3: lb_rn1[3] was just updated to pixels[67]=169 (if read-after-write)
# Then rn1 = 169 instead of 167.
# win = [155,155,155, 169,169,169, 169,169,169]
win_raw = [155,155,155, 169,169,169, 169,169,169]
print("read-after-write lb_rn1:", hex(sobel_compute(win_raw)[2]))

# What if lb_rn2 reads the new value? At row=2, col=3:
# lb_rn2[3] was updated to old lb_rn1[3] = 167 (if read-after-write on lb_rn2)
# But old lb_rn1[3] = 167, so rn2 = 167 instead of 155.
# win = [167,167,167, 167,167,167, 169,169,169]
win_raw2 = [167,167,167, 167,167,167, 169,169,169]
print("read-after-write lb_rn2:", hex(sobel_compute(win_raw2)[2]))

# Hmm, none of these give 156. Let me try other combinations.
# What if the shift register is off by one? sr2_1 has the wrong value.
# Let me try: win = [155,155,155, 167,167,167, 167,169,169] (sr2_1=167 instead of 169)
win_sr = [155,155,155, 167,167,167, 167,169,169]
print("sr2_1 off by one:", hex(sobel_compute(win_sr)[2]))