import json, os, sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.sobel_core import sobel_compute
from model.params import IMG_W, IMG_H
px = json.load(open('context/chip_input_grid.json'))['pixels']
flat=[p for row in px for p in row]

# Replicate the streaming model but trace
lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)
win = Window3x3()
results=[]
for idx, p in enumerate(flat):
    row=idx//IMG_W; col=idx%IMG_W
    lb0_data = lb0.tap(col) if row>=2 else 0
    lb1_data = lb1.tap(col) if row>=1 else 0
    w, valid = win.step(1,1,1,p,lb0_data,lb1_data,col,row)
    lb1.step(1,1,1, lb0.row[-1] if row>=1 else 0)
    lb0.step(1,1,1, p)
    if valid:
        gx,gy,o=sobel_compute(w)
        results.append((idx,row,col,w,o))
        if len(results)<=3:
            print('idx',idx,'r',row,'c',col,'win',w,'out',o)
            print('  lb0_data',lb0_data,'lb1_data',lb1_data)