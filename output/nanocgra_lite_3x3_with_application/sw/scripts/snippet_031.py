import json, os
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ---- Derive canonical 32x32 input by DOWNSCALING THE WHOLE image ----
src = "context/uploads/Screenshot_from_2026-07-14_16-24-31.png"
img = Image.open(src).convert("RGB")
W, H = img.size
print("original size:", W, H)

# Grayscale (ITU-R BT.601) on the FULL image
g = img.convert("L")  # PIL L uses L = 299/1000 R + 587/1000 G + 114/1000 B

# Downscale the WHOLE grayscale image to 32x32 (nearest is fine for the grid,
# but use default (LANCZOS/bilinear) for the actual data to keep scene recognizable)
N = 32
grid = g.resize((N, N), Image.BILINEAR)
pixels = np.array(grid, dtype=np.uint8)  # 32x32

# Save canonical input json
flat2d = pixels.tolist()
with open("context/chip_input_grid.json", "w") as f:
    json.dump({"N": N, "pixels": flat2d}, f)

# Save rtl/sobel_input.mem (1024 hex bytes, one per line)
flat = pixels.flatten().tolist()
with open("rtl/sobel_input.mem", "w") as f:
    f.write("\n".join(f"{v:02x}" for v in flat) + "\n")

print("input min/max/mean:", pixels.min(), pixels.max(), round(float(pixels.mean()),1))
print("wrote context/chip_input_grid.json and rtl/sobel_input.mem  (", len(flat), "bytes )")

# ---- Visualization: side-by-side original | grayscale | 32x32 grid (upscaled) ----
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
axes[0].imshow(img); axes[0].set_title("Original upload"); axes[0].axis('off')
axes[1].imshow(g, cmap='gray'); axes[1].set_title("Grayscale (full)"); axes[1].axis('off')
axes[2].imshow(grid.resize((256,256), Image.NEAREST), cmap='gray')
axes[2].set_title("32x32 grid (chip input, NN-upscaled)"); axes[2].axis('off')
plt.tight_layout()
os.makedirs("waves", exist_ok=True)
plt.savefig("waves/chip_input.png", dpi=110, bbox_inches='tight')
print("saved waves/chip_input.png")