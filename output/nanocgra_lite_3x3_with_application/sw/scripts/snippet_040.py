import json, sys
sys.path.insert(0,'golden')
from model.line_buffer import LineBuffer
from model.params import IMG_W
px = json.load(open('context/chip_input_grid.json'))['pixels']
flat=[p for row in px for p in row]

# Trace lb0 and lb1 contents at end of each row
lb0 = LineBuffer(IMG_W)
lb1 = LineBuffer(IMG_W)
for idx, p in enumerate(flat):
    row=idx//IMG_W; col=idx%IMG_W
    lb1.step(1,1,1, lb0.row[-1] if row>=1 else 0)
    lb0.step(1,1,1, p)
    if col==IMG_W-1 and row<=3:
        print(f'end row {row}: lb0[:4]={lb0.row[:4]} lb1[:4]={lb1.row[:4]}')
        print(f'  actual row{row}[:4]={px[row][:4]}')
        print(f'  lb0[-1]={lb0.row[-1]} (last element, oldest)')
        print(f'  lb1[-1]={lb1.row[-1]}')