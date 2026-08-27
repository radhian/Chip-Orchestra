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
        print(f'end row {row}: lb0[0]={lb0.row[0]} lb0[1]={lb0.row[1]} lb0[2]={lb0.row[2]}')
        print(f'  actual row{row}[0:3]={px[row][0:3]}')
        print(f'  lb1[0]={lb1.row[0]} lb1[1]={lb1.row[1]} lb1[2]={lb1.row[2]}')
        print(f'  actual row{row-1}[0:3]={px[row-1][0:3] if row>=1 else "NA"}')
        print(f'  lb0[-1]={lb0.row[-1]} (oldest, should be px[row][31])')
        print(f'  actual px[{row}][31]={px[row][31]}')