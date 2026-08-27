import json, sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.params import IMG_W
px = json.load(open('context/chip_input_grid.json'))['pixels']
flat=[p for row in px for p in row]

lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)
win = Window3x3()
# trace first valid window at idx66 (r2,c2)
for idx, p in enumerate(flat):
    row=idx//IMG_W; col=idx%IMG_W
    lb0_data = lb0.tap(col) if row>=2 else 0
    lb1_data = lb1.tap(col) if row>=1 else 0
    w, valid = win.step(1,1,1,p,lb0_data,lb1_data,col,row)
    if idx==65:
        print('before idx66: idx',idx,'r',row,'c',col)
        print('  lb0.row',lb0.row[:5])
        print('  lb1.row',lb1.row[:5])
        print('  lb0.tap(2)',lb0.tap(2),'lb1.tap(2)',lb1.tap(2))
        print('  px[0][2]',px[0][2],'px[1][2]',px[1][2],'px[2][2]',px[2][2])
    lb1.step(1,1,1, lb0.row[-1] if row>=1 else 0)
    lb0.step(1,1,1, p)
    if idx==65:
        print('after idx65 step:')
        print('  lb0.row[:5]',lb0.row[:5])
        print('  lb1.row[:5]',lb1.row[:5])