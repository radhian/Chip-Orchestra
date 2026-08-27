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
print("after row0: lb0[:4]=",lb0.row[:4], "(should be row0:",px[0][:4],")")
# row1: lb1 gets lb0 (row0), lb0 gets row1
for col in range(IMG_W):
    lb1.step(1,1,1, lb0.row[-1])  # WRONG - only gets last element
    lb0.step(1,1,1, px[1][col])
print("after row1: lb0[:4]=",lb0.row[:4], "(row1:",px[1][:4],")")
print("           lb1[:4]=",lb1.row[:4], "(row0:",px[0][:4],")")