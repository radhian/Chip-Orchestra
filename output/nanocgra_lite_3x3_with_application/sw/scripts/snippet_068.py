import json, os, sys
sys.path.insert(0, 'golden')
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.sobel_core import sobel_compute
from model.params import IMG_W

path = os.path.join('context', 'chip_input_grid.json')
with open(path) as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]

# The window at col=3 has lb0_data=168 but expected 167 (pixels_2d[1][3]=167)
# lb0 holds row 1. lb0.tap(3) should be pixels_2d[1][3]=167
# But we got 168. Let me check: 168 = pixels_2d[2][3]? No, pixels_2d[2][3]=169
# Actually 168 might be pixels_2d[1][4]... let me check
print("pixels_2d[1][3:6]=", pixels_2d[1][3:6])
print("pixels_2d[2][3:6]=", pixels_2d[2][3:6])

# The issue: lb0 is being shifted with px (current row N pixel) BEFORE we tap it at the next col
# Wait no, we tap BEFORE shift. Let me trace lb0 contents at row 2, col 3
lb0 = LineBuffer(IMG_W)  # row N-1
lb1 = LineBuffer(IMG_W)  # row N-2

for idx, px in enumerate(flat[:100]):
    row = idx // IMG_W
    col = idx % IMG_W
    lb1_data = lb1.tap(col) if row >= 2 else 0
    lb0_data = lb0.tap(col) if row >= 1 else 0
    if row == 2 and col == 3:
        print(f"BEFORE shift at idx={idx}: lb0.row[0:6]={lb0.row[0:6]}")
        print(f"  lb0.tap(3)={lb0.tap(3)}")
    lb1.step(1, 1, 1, lb0_data if row >= 1 else 0)
    lb0.step(1, 1, 1, px)
    if row == 2 and col == 3:
        print(f"AFTER shift at idx={idx}: lb0.row[0:6]={lb0.row[0:6]}")
        print(f"  px={px}")

# The problem: at row 1, lb0 was loaded with row 1's pixels. But the transfer lb1.step(lb0_data) 
# happens at the SAME time lb0.step(px). So during row 1, lb0 gets row 1 pixels, lb1 gets row 0 pixels.
# At row 2, lb0 should still hold row 1. But lb0 is getting row 2 pixels pushed in!
# So at row 2 col 3, lb0 has been shifted with row 2 pixels for cols 0,1,2,3
# lb0.tap(3) = the value at position 3, which was pushed in at col 3 of row 2 = px=169? No...

# Let me trace lb0 at end of row 1 and start of row 2
lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)
for idx, px in enumerate(flat[:100]):
    row = idx // IMG_W
    col = idx % IMG_W
    lb1_data = lb1.tap(col) if row >= 2 else 0
    lb0_data = lb0.tap(col) if row >= 1 else 0
    lb1.step(1, 1, 1, lb0_data if row >= 1 else 0)
    lb0.step(1, 1, 1, px)
    if (row == 1 and col == 31) or (row == 2 and col <= 4):
        print(f"idx={idx} row={row} col={col}: lb0.row[0:6]={lb0.row[0:6]}")