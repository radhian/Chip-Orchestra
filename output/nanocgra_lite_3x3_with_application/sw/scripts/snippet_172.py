import json, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream

with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = grid['pixels']
flat = [p for row in pixels for p in row]

# Sobel at output index 0 = window at row=2,col=2
# window pixels: rows 0,1,2 cols 0,1,2
def get(r,c): return flat[r*32+c]

w = [get(0,0),get(0,1),get(0,2),
     get(1,0),get(1,1),get(1,2),
     get(2,0),get(2,1),get(2,2)]
print("window0:", w)
gx = -w[0]+w[2]-2*w[3]+2*w[5]-w[6]+w[8]
gy = -w[0]-2*w[1]-w[2]+w[6]+2*w[7]+w[8]
mag = abs(gx)+abs(gy)
print("gx=",gx,"gy=",gy,"mag=",mag,"out=",min(mag,255))

# index 1 = row=2, col=3
w1 = [get(0,1),get(0,2),get(0,3),
      get(1,1),get(1,2),get(1,3),
      get(2,1),get(2,2),get(2,3)]
gx = -w1[0]+w1[2]-2*w1[3]+2*w1[5]-w1[6]+w1[8]
gy = -w1[0]-2*w1[1]-w1[2]+w1[6]+2*w1[7]+w1[8]
mag = abs(gx)+abs(gy)
print("window1:", w1, "out=", min(mag,255))