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
    # SWAP: lb0 = row N-1, lb1 = row N-2
    lb0_data = lb1.tap(col) if row>=2 else 0  # row N-2 from lb1
    lb1_data = lb0.tap(col) if row>=1 else 0  # row N-1 from lb0
    w,valid = win.step(1,1,1,p,lb0_data,lb1_data,col,row)
    # shift: lb1 (N-2) gets lb0 (N-1) content, lb0 (N-1) gets current
    lb1.step(1,1,1, lb0.tap(col) if row>=1 else 0)
    lb0.step(1,1,1,p)
    if valid:
        results.append((row,col,w,sobel_compute(w)[2]))
print("Expected win (2,2):", [px[0][0],px[0][1],px[0][2],px[1][0],px[1][1],px[1][2],px[2][0],px[2][1],px[2][2]])
print("Got win (2,2):", results[0][2])
ref=[]
for y in range(30):
    for x in range(30):
        w=[px[y+r][x+c] for r in range(3) for c in range(3)]
        _,_,o=sobel_compute(w)
        ref.append(o)
out=[r[3] for r in results]
print("match:", out==ref)
print("out[:6]=",out[:6])
print("ref[:6]=",ref[:6])