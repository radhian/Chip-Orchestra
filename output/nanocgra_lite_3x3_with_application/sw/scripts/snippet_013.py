import sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
import json
with open('context/chip_input_grid.json') as f: d=json.load(f)
px=d['pixels']
IMG_W=32
lb0=LineBuffer(IMG_W); lb1=LineBuffer(IMG_W)
# Feed rows 0,1,2 and inspect lb0 contents after each row
for row in range(3):
    for col in range(IMG_W):
        p=px[row][col]
        lb1.step(1,1,1, lb0.row[-1] if row>=1 else 0)
        lb0.step(1,1,1,p)
    print("after row",row,"lb0.row[0:6]=",lb0.row[0:6],"lb1.row[0:6]=",lb1.row[0:6])
print("px row0[0:6]=",px[0][0:6])
print("px row1[0:6]=",px[1][0:6])
print("px row2[0:6]=",px[2][0:6])