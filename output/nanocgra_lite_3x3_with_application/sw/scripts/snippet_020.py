import sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.sobel_core import sobel_compute
import json
with open('context/chip_input_grid.json') as f: d=json.load(f)
px=d['pixels']
IMG_W=32
lb0=LineBuffer(IMG_W); lb1=LineBuffer(IMG_W)
win=Window3x3()
results=[]
for idx,p in enumerate([p for row in px for p in row]):
    row=idx//IMG_W; col=idx%IMG_W
    # tap BEFORE shift: lb0 has row N-2, lb1 has row N-1
    lb0_data = lb0.tap(col) if row>=2 else 0
    lb1_data = lb1.tap(col) if row>=1 else 0
    w,valid = win.step(1,1,1,p,lb0_data,lb1_data,col,row)
    # shift lb0 first into lb1, then lb0
    lb1.step(1,1,1, lb0.tap(col) if row>=1 else 0)
    lb0.step(1,1,1,p)
    if valid:
        results.append((row,col,w,sobel_compute(w)[2]))

# Check what window we get at (2,2) - should be rows 0,1,2 cols 0,1,2
print("Expected win (2,2):", [px[0][0],px[0][1],px[0][2],px[1][0],px[1][1],px[1][2],px[2][0],px[2][1],px[2][2]])
print("Got win (2,2):", results[0][2])