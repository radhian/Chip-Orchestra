import json, os
from golden.model.sobel_core import sobel_compute
px = json.load(open('context/chip_input_grid.json'))['pixels']
# reference computation for pixel (0,0)
w = [px[r][c] for r in range(3) for c in range(3)]
print('window', w)
gx,gy,o = sobel_compute(w)
print('gx',gx,'gy',gy,'out',o)
# Now run the streaming model
from golden.model.top import sobel_stream
flat=[p for row in px for p in row]
out=sobel_stream(flat)
print('stream out[0:6]', out[:6])
# reference loop
ref=[]
for y in range(30):
    for x in range(30):
        w=[px[y+r][x+c] for r in range(3) for c in range(3)]
        _,_,o=sobel_compute(w)
        ref.append(o)
print('ref   out[0:6]', ref[:6])
print('match', out==ref)