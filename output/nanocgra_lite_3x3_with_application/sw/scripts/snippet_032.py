import sys, os, json
sys.path.insert(0, "golden")
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from model.top import sobel_stream
from model.params import IMG_W, IMG_H, OUT_W, OUT_H

# Load canonical input
with open("context/chip_input_grid.json") as f:
    data = json.load(f)
pixels_2d = data['pixels']
flat = [p for row in pixels_2d for p in row]
assert len(flat) == IMG_W*IMG_H, len(flat)

# Run toplevel golden model
out = sobel_stream(flat)
assert len(out) == OUT_W*OUT_H, (len(out), OUT_W*OUT_H)
out_arr = np.array(out, dtype=np.uint8).reshape(OUT_H, OUT_W)
in_arr  = np.array(flat, dtype=np.uint8).reshape(IMG_H, IMG_W)

print("output min/max/mean:", int(out_arr.min()), int(out_arr.max()), round(float(out_arr.mean()),2))
print("nonzero output pixels:", int((out_arr>0).sum()), "/", OUT_W*OUT_H)

# Save golden_output.mem (900 hex bytes, row-major) — SAME N*N row-major hex format
os.makedirs("waves", exist_ok=True)
with open("waves/golden_output.mem", "w") as f:
    f.write("\n".join(f"{v:02x}" for v in out) + "\n")
print("wrote waves/golden_output.mem (", len(out), "bytes )")

# Render golden_output.png
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
axes[0].imshow(in_arr, cmap='gray'); axes[0].set_title("Input 32x32"); axes[0].axis('off')
axes[1].imshow(out_arr, cmap='gray'); axes[1].set_title("Sobel output 30x30"); axes[1].axis('off')
plt.tight_layout()
plt.savefig("waves/golden_output.png", dpi=110, bbox_inches='tight')
print("saved waves/golden_output.png")

# Dump headline numbers to golden/outputs/<name>.json
os.makedirs("golden/outputs", exist_ok=True)
headline = {
    "input": "context/uploads/Screenshot_from_2026-07-14_16-24-31.png",
    "framing": "whole image downscaled to 32x32 grayscale (BILINEAR), no crop",
    "input_size": [IMG_W, IMG_H],
    "output_size": [OUT_W, OUT_H],
    "output_min": int(out_arr.min()),
    "output_max": int(out_arr.max()),
    "output_mean": round(float(out_arr.mean()), 3),
    "nonzero_output_pixels": int((out_arr>0).sum()),
    "total_output_pixels": int(OUT_W*OUT_H),
}
with open("golden/outputs/sobel_result.json", "w") as f:
    json.dump(headline, f, indent=2)
print("wrote golden/outputs/sobel_result.json")
print(json.dumps(headline, indent=2))