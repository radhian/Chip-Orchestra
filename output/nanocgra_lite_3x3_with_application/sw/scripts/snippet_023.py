import sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
import json
with open('context/chip_input_grid.json') as f: d=json.load(f)
px=d['pixels']
IMG_W=32
# lb0 = row N-1, lb1 = row N-2
lb0=LineBuffer(IMG_W); lb1=LineBuffer(IMG_W)
for idx,p in enumerate([p for row in px for p in row]):
    row=idx//IMG_W; col=idx%IMG_W
    if row==2 and col in (2,3,4):
        print(f"col={col}: lb0(N-1)[col]={lb0.tap(col)} lb1(N-2)[col]={lb1.tap(col)} cur={p}")
        print(f"  lb0.row[0:5]={lb0.row[0:5]} lb1.row[0:5]={lb1.row[0:5]}")
    # shift
    lb1.step(1,1,1, lb0.tap(col) if row>=1 else 0)
    lb0.step(1,1,1,p)
    if row==2 and col==4: break