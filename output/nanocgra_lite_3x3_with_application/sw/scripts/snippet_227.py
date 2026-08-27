import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]
IMG_W = 32
def get_pixel(r, c):
    return pixels[r*IMG_W + c]

# The golden stream out[0] window is [151,155,155, 165,167,167, 167,169,169]
# This is rows 0,1,2 cols 0,1,2 — centered at (1,1)!! Not (2,2).
# So the golden streaming model uses a window where:
#   row N-2 = row 0, row N-1 = row 1, row N = row 2
#   col c-2, c-1, c = 0,1,2
# So the "center" of the window is (1,1), and the output is emitted when row=2,col=2
# but the window covers rows 0,1,2 and cols 0,1,2.
# This means the output grid is 30x30 where output[r][c] corresponds to window
# with top-left at (r, c), i.e., centered at (r+1, c+1).

# Let's verify: golden out[0] = 0x44 = 68
# window [151,155,155, 165,167,167, 167,169,169]
def sobel_compute(win):
    w = [int(x) & 0xFF for x in win]
    gx = (-w[0] + w[2] - 2*w[3] + 2*w[5] - w[6] + w[8])
    gy = (-w[0] - 2*w[1] - w[2] + w[6] + 2*w[7] + w[8])
    mag = abs(gx) + abs(gy)
    out = max(0, min(255, mag))
    return gx, gy, out

win = [151,155,155, 165,167,167, 167,169,169]
print("golden out[0] check:", hex(sobel_compute(win)[2]))

# Now the chip produces 0x9c = 156 for index 0 (from the log: index 1: golden=0x38 chip=0x9c)
# Wait, the log says index 1: golden=0x38 chip=0x9c. Let me check what window gives 0x9c.
# The chip seems to be off. Let me check: 0x9c = 156. 
# What if the chip uses rows 1,2,3 cols 1,2,3 (centered at 2,2)?
win2 = [get_pixel(1,1),get_pixel(1,2),get_pixel(1,3), get_pixel(2,1),get_pixel(2,2),get_pixel(2,3), get_pixel(3,1),get_pixel(3,2),get_pixel(3,3)]
print("chip candidate (center 2,2):", win2, "->", hex(sobel_compute(win2)[2]))

# What about rows 0,1,2 cols 1,2,3?
win3 = [get_pixel(0,1),get_pixel(0,2),get_pixel(0,3), get_pixel(1,1),get_pixel(1,2),get_pixel(1,3), get_pixel(2,1),get_pixel(2,2),get_pixel(2,3)]
print("chip candidate (top-left 0,1):", win3, "->", hex(sobel_compute(win3)[2]))

# 0x9c = 156. Let me search what window gives 156
# Actually, let me check the chip value for index 0. The log shows index 1 first.
# The summary says: index 1: golden=0x38 chip=0x9c
# But the MISMATCH log starts at index 5. Let me check index 0.
# From "First 10 chip outputs" we'd need to see the sim log. Let me check the mem files.