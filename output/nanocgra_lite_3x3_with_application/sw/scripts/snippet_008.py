import numpy as np, json
arr = np.array(json.load(open('context/chip_input_grid.json'))['pixels'], dtype=np.int32)
# Sobel
gx = np.zeros((30,30), dtype=np.int32)
gy = np.zeros((30,30), dtype=np.int32)
for y in range(30):
    for x in range(30):
        w = arr[y:y+3, x:x+3]
        gx[y,x] = (-w[0,0] + w[0,2] - 2*w[1,0] + 2*w[1,2] - w[2,0] + w[2,2])
        gy[y,x] = (-w[0,0] - 2*w[0,1] - w[0,2] + w[2,0] + 2*w[2,1] + w[2,2])
mag = np.abs(gx) + np.abs(gy)
out = np.clip(mag, 0, 255).astype(np.uint8)
print('out shape', out.shape, 'min', out.min(), 'max', out.max(), 'mean', out.mean())
print('sample out[0,:5]', out[0,:5].tolist())
print('sample out[15,:5]', out[15,:5].tolist())