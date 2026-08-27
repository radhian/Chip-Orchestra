import numpy as np

with open('rtl/sobel_input.mem') as f:
    inp = np.array([int(l.strip(),16) for l in f if l.strip()], dtype=np.int32).reshape(32,32)

def sobel(img):
    h,w = img.shape
    out = np.zeros((h-2,w-2), dtype=np.uint8)
    for y in range(1,h-1):
        for x in range(1,w-1):
            w0=img[y-1,x-1]; w1=img[y-1,x]; w2=img[y-1,x+1]
            w3=img[y,x-1];             w5=img[y,x+1]
            w6=img[y+1,x-1]; w7=img[y+1,x]; w8=img[y+1,x+1]
            gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
            gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
            mag = abs(gx)+abs(gy)
            out[y-1,x-1] = min(mag,255)
    return out

gold = sobel(inp)
with open('rtl/sobel_golden.mem') as f:
    disk = np.array([int(l.strip(),16) for l in f if l.strip()], dtype=np.uint8).reshape(30,30)

print('golden match:', np.array_equal(gold, disk))
diff = gold.astype(int)-disk.astype(int)
print('num diff:', np.count_nonzero(diff))
idx = np.argwhere(diff!=0)
print('first diffs:', idx[:10])
for i in idx[:5]:
    y,x=i
    print(f'  ({y},{x}) gold={gold[y,x]} disk={disk[y,x]}')