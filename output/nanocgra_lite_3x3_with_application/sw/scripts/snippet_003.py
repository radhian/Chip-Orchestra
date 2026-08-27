from PIL import Image
import numpy as np

img2 = Image.open('context/uploads/Screenshot_from_2026-07-14_16-24-31.png')
arr = np.array(img2.convert('L'))

# Let's scan more broadly to find a crop with good edge content (road with lane markings + vehicles)
# The road with lane dividers would have high contrast (white lines on dark asphalt)
best = []
for cy in range(250, 400, 10):
    for cx in range(0, 600, 20):
        crop = arr[cy:cy+32, cx:cx+32]
        if crop.shape == (32, 32):
            # Sobel edge magnitude as proxy
            score = crop.std()  # variance indicates edges/features
            best.append((score, cx, cy, crop.mean()))

best.sort(reverse=True)
print("Top crops by std (edge content):")
for s, cx, cy, m in best[:10]:
    print(f"  ({cx},{cy}) std={s:.1f} mean={m:.1f}")

# Save the best crop for visualization
s, cx, cy, m = best[0]
crop_img = img2.crop((cx, cy, cx+32, cy+32))
crop_img.save('context/best_crop_preview.png')
print(f"\nBest crop saved: ({cx},{cy}) -> context/best_crop_preview.png")

# Also save a few candidates
for i, (s, cx, cy, m) in enumerate(best[:5]):
    crop_img = img2.crop((cx, cy, cx+32, cy+32))
    crop_img.save(f'context/crop_candidate_{i}.png')