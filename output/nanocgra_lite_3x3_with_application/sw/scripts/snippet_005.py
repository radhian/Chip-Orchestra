from PIL import Image
import numpy as np

img2 = Image.open('context/uploads/Screenshot_from_2026-07-14_16-24-31.png').convert('RGB')
arr = np.array(img2.convert('L'))

# Let's find a crop that clearly shows the road with vehicles and lane markings
# The red SUV should have high R channel. Let's scan for crops with high R variance (red vehicle on road)
best_road = []
for cy in range(260, 420, 5):
    for cx in range(0, 500, 5):
        crop = arr[cy:cy+32, cx:cx+32]
        if crop.shape == (32, 32):
            # Want road (moderate-dark) with features (lane lines, vehicles)
            # Score: high std (edges) + mean in road range (40-120)
            score = crop.std()
            mean = crop.mean()
            if 40 < mean < 130:  # road-like brightness
                best_road.append((score, cx, cy, mean))

best_road.sort(reverse=True)
print("Top road crops:")
for s, cx, cy, m in best_road[:8]:
    print(f"  ({cx},{cy}) std={s:.1f} mean={m:.1f}")

# Pick one that shows road with lane markings and vehicles
# (20,340) looks good - road with red SUV area
# Let's save the chosen crop
cx, cy = 20, 340
crop_img = img2.crop((cx, cy, cx+32, cy+32))
crop_gray = arr[cy:cy+32, cx:cx+32]
crop_img.save('context/chosen_crop.png')
print(f"\nChosen crop ({cx},{cy}) saved. Grayscale values:")
print(crop_gray)