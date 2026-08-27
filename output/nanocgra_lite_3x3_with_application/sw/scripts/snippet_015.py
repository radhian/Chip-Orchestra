import sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
import json
with open('context/chip_input_grid.json') as f: d=json.load(f)
px=d['pixels']
IMG_W=32
lb0=LineBuffer(IMG_W); lb1=LineBuffer(IMG_W)
# Trace row 2, col 0..2
for idx,p in enumerate([p for row in px for p in row]):
    row=idx//IMG_W; col=idx%IMG_W
    if row<2: 
        lb1.step(1,1,1, lb0.row[-1] if row>=1 else 0)
        lb0.step(1,1,1,p)
        continue
    if row==2 and col<=2:
        lb0_data=lb0.tap(col)
        lb1_data=lb1.tap(col)
        print(f"before shift row={row} col={col}: lb0[{col}]={lb0_data} lb1[{col}]={lb1_data} cur={p}")
        print(f"  lb0.row[0:4]={lb0.row[0:4]} lb1.row[0:4]={lb1.row[0:4]}")
        lb1.step(1,1,1, lb0.row[-1])
        lb0.step(1,1,1,p)
        if col==2:
            break
    else:
        lb1.step(1,1,1, lb0.row[-1])
        lb0.step(1,1,1,p)