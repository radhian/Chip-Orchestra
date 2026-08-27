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

# Trace at (2,2) with lb0=row N-1, lb1=row N-2
lb0 = LineBuffer(IMG_W)  # row N-1
lb1 = LineBuffer(IMG_W)  # row N-2
win = Window3x3()

for idx, px in enumerate(flat[:67]):
    row = idx // IMG_W
    col = idx % IMG_W
    lb1_data = lb1.tap(col) if row >= 2 else 0  # row N-2
    lb0_data = lb0.tap(col) if row >= 1 else 0  # row N-1
    w, valid = win.step(1, 1, 1, px, lb1_data, lb0_data, col, row)
    lb1.step(1, 1, 1, lb0_data if row >= 1 else 0)
    lb0.step(1, 1, 1, px)
    if row == 2 and col <= 2:
        print(f"idx={idx} row={row} col={col} px={px}")
        print(f"  lb1(rowN-2)_data={lb1_data} lb0(rowN-1)_data={lb0_data}")
        print(f"  lb1.row[0:4]={lb1.row[0:4]}")
        print(f"  lb0.row[0:4]={lb0.row[0:4]}")
        if valid:
            print(f"  window={w}")
            print(f"  expected={[pixels_2d[0][0],pixels_2d[0][1],pixels_2d[0][2],pixels_2d[1][0],pixels_2d[1][1],pixels_2d[1][2],pixels_2d[2][0],pixels_2d[2][1],pixels_2d[2][2]]}")