import sys, os
sys.path.insert(0, 'golden')
from model.sobel_core import sobel_compute
import json
with open('context/chip_input_grid.json') as f: d=json.load(f)
px=d['pixels']
# reference for pixel (0,0)
w=[px[y][x] for y in range(3) for x in range(3)]
print("window (0,0):", w)
gx,gy,o = sobel_compute(w)
print("ref (0,0):", gx, gy, o)

# Now run sobel_stream
from model.top import sobel_stream
flat=[p for row in px for p in row]
out=sobel_stream(flat)
print("stream first 10:", out[:10])

# reference full
ref=[]
for y in range(30):
    for x in range(30):
        w=[px[y+r][x+c] for r in range(3) for c in range(3)]
        _,_,o=sobel_compute(w)
        ref.append(o)
print("ref first 10:", ref[:10])
print("match:", out==ref)