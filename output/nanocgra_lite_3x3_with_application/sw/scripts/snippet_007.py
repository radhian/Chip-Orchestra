import os, json, numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Paths
src = 'context/uploads/Screenshot_from_2026-07-14_16-24-31.png'
N = 32

# Load and convert to grayscale, then downscale to NxN (NO crop)
img = Image.open(src).convert('L')
img_rgb = Image.open(src).convert('RGB')
small = img.resize((N, N), Image.BILINEAR)  # grayscale NxN
arr = np.array(small, dtype=np.uint8)  # (N, N)

# Save hex mem (row-major, one byte per line)
os.makedirs('rtl', exist_ok=True)
os.makedirs('waves', exist_ok=True)
os.makedirs('context', exist_ok=True)
os.makedirs('golden/outputs', exist_ok=True)
os.makedirs('golden/model', exist_ok=True)
os.makedirs('golden/tests', exist_ok=True)
os.makedirs('golden/vectors', exist_ok=True)

with open('rtl/sobel_input.mem', 'w') as f:
    for y in range(N):
        for x in range(N):
            f.write(f'{arr[y,x]:02x}\n')

# Save grid json
with open('context/chip_input_grid.json', 'w') as f:
    json.dump({'N': N, 'pixels': arr.tolist()}, f)

# Side length
with open('context/input_size.txt', 'w') as f:
    f.write(f'{N}\n')

# Visualization: original, grayscale, NxN upscaled
fig, axes = plt.subplots(1, 3, figsize=(12, 4))
axes[0].imshow(img_rgb); axes[0].set_title('Original upload'); axes[0].axis('off')
axes[1].imshow(img, cmap='gray'); axes[1].set_title('Grayscale'); axes[1].axis('off')
up = small.resize((256, 256), Image.NEAREST)
axes[2].imshow(up, cmap='gray'); axes[2].set_title(f'{N}x{N} grid (chip input)'); axes[2].axis('off')
plt.tight_layout()
plt.savefig('waves/chip_input.png', dpi=100)
plt.close()

print('Input generated:', arr.shape, 'min', arr.min(), 'max', arr.max())
print('Mean:', arr.mean())
print('First row:', arr[0].tolist())
print('Saved rtl/sobel_input.mem, context/chip_input_grid.json, context/input_size.txt, waves/chip_input.png')