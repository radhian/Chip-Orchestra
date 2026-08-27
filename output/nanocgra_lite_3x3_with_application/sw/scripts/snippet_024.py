import sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
import json
with open('context/chip_input_grid.json') as f: d=json.load(f)
px=d['pixels']
IMG_W=32
lb0=LineBuffer(IMG_W); lb1=LineBuffer(IMG_W)
# row0: lb0 gets row0
for col in range(IMG_W):
    lb0.step(1,1,1, px[0][col])
print("after row0: lb0[:5]=",lb0.row[:5], "row0[:5]=",px[0][:5])
# row1: lb1 gets lb0 tap, lb0 gets row1
for col in range(IMG_W):
    lb1.step(1,1,1, lb0.tap(col))
    lb0.step(1,1,1, px[1][col])
print("after row1: lb0[:5]=",lb0.row[:5], "row1[:5]=",px[1][:5])
print("           lb1[:5]=",lb1.row[:5], "row0[:5]=",px[0][:5])
# row2: lb1 gets lb0 tap, lb0 gets row2
for col in range(IMG_W):
    if col<5:
        print(f"  col={col}: lb0(N-1)[{col}]={lb0.tap(col)} lb1(N-2)[{col}]={lb1.tap(col)} cur={px[2][col]}")
    lb1.step(1,1,1, lb0.tap(col))
    lb0.step(1,1,1, px[2][col])
    if col==4:
        print("after row2 col4: lb0[:5]=",lb0.row[:5],"row2[:5]=",px[2][:5])
        print("                lb1[:5]=",lb1.row[:5],"row1[:5]=",px[1][:5])
        break