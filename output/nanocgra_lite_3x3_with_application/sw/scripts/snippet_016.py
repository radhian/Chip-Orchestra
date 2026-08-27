import sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
import json
with open('context/chip_input_grid.json') as f: d=json.load(f)
px=d['pixels']
IMG_W=32
lb0=LineBuffer(IMG_W); lb1=LineBuffer(IMG_W)
# Trace carefully. lb0 = row N-2, lb1 = row N-1
for idx,p in enumerate([p for row in px for p in row]):
    row=idx//IMG_W; col=idx%IMG_W
    if row==0:
        # lb0 gets row0. lb1 gets lb0's oldest (but lb0 empty/old)
        lb1.step(1,1,1, lb0.row[-1])  # lb1 gets garbage (lb0 old last)
        lb0.step(1,1,1,p)  # lb0 = row0
    elif row==1:
        # lb1 should get row0 (lb0's content), lb0 gets row1
        lb1.step(1,1,1, lb0.row[-1])  # lb1 gets row0's last? NO - whole shift
        lb0.step(1,1,1,p)  # lb0 = row1
    elif row==2:
        if col==0:
            print("start row2: lb0(row1)=",lb0.row[:4], "lb1=",lb1.row[:4])
        # tap
        lb0_data=lb0.tap(col); lb1_data=lb1.tap(col)
        if col<=2:
            print(f"col={col}: lb0_data(row1)={lb0_data} lb1_data(row0)={lb1_data} cur(row2)={p}")
        lb1.step(1,1,1, lb0.row[-1])
        lb0.step(1,1,1,p)
        if col==2: break