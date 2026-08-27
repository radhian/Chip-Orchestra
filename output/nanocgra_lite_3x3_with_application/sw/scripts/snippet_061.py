import json, os, sys
sys.path.insert(0, 'golden')
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.params import IMG_W

path = os.path.join('context', 'chip_input_grid.json')
with open(path) as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]

lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)
win = Window3x3()

# Trace rows 0-2, cols 0-2
for idx, px in enumerate(flat[:3*IMG_W + 3]):  # first 3 rows + 3 cols
    row = idx // IMG_W
    col = idx % IMG_W
    lb0_data = lb0.tap(col) if row >= 2 else 0
    lb1_data = lb1.tap(col) if row >= 1 else 0
    w2, valid = win.step(1, 1, 1, px, lb0_data, lb1_data, col, row)
    lb1.step(1, 1, 1, lb0.row[-1] if row >= 1 else 0)
    lb0.step(1, 1, 1, px)
    if row < 3 and col < 4:
        print(f"idx={idx} row={row} col={col} px={px} lb0_data={lb0_data} lb1_data={lb1_data} valid={valid}")
        if valid:
            print(f"   window={w2}")
        print(f"   lb0.row[0:4]={lb0.row[0:4]} lb1.row[0:4]={lb1.row[0:4]}")