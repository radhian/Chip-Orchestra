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
    lb0_data = lb0.tap(col) if row>=2 else 0
    lb1_data = lb1.tap(col) if row>=1 else 0
    w,valid = win.step(1,1,1,p,lb0_data,lb1_data,col,row)
    # CORRECT order: shift lb0 first (into lb1), then lb0
    lb1.step(1,1,1, lb0.row[-1] if row>=1 else 0)
    lb0.step(1,1,1,p)
    if valid:
        results.append((row,col,w,sobel_compute(w)[2]))
for r in results[:3]:
    print("row",r[0],"col",r[1],"win",r[2],"out",r[3])

# Now the CORRECT version: tap BEFORE shifting, but tap from the RIGHT line buffers
# lb0 should hold row N-2, lb1 row N-1. Let's re-derive with correct assignment.
print("=== corrected ===")
lb0=LineBuffer(IMG_W); lb1=LineBuffer(IMG_W)
win=Window3x3()
results=[]
for idx,p in enumerate([p for row in px for p in row]):
    row=idx//IMG_W; col=idx%IMG_W
    # tap from line buffers BEFORE shifting
    lb0_data = lb0.tap(col) if row>=2 else 0
    lb1_data = lb1.tap(col) if row>=1 else 0
    w,valid = win.step(1,1,1,p,lb0_data,lb1_data,col,row)
    # shift: lb1 gets lb0's oldest, lb0 gets current pixel
    lb1.step(1,1,1, lb0.row[-1] if row>=1 else 0)
    lb0.step(1,1,1,p)
    if valid:
        results.append((row,col,w,sobel_compute(w)[2]))
for r in results[:3]:
    print("row",r[0],"col",r[1],"win",r[2],"out",r[3])