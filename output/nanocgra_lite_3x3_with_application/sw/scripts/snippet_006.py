from PIL import Image
import numpy as np

img2 = Image.open('context/uploads/Screenshot_from_2026-07-14_16-24-31.png').convert('RGB')
arr = np.array(img2.convert('L'))

# The crop at (20,340) shows road with a bright transition (likely the red SUV edge / hood)
# Let's check a crop that captures more of the road with lane markings
# Let's look at the area around x=150-200, y=270-300 where the black and white cars are
for (cx, cy) in [(150, 270), (160, 275), (170, 270), (180, 275), (190, 270), (200, 275)]:
    crop = arr[cy:cy+32, cx:cx+32]
    print(f"({cx},{cy}): mean={crop.mean():.1f} std={crop.std():.1f}")

# Let's also check the lane divider area - white dashed lines
# Lane dividers in left lanes around x=200-300 in original 1920 -> scaled x=100-150
for (cx, cy) in [(100, 300), (120, 300), (140, 300), (100, 320), (120, 320)]:
    crop = arr[cy:cy+32, cx:cx+32]
    print(f"({cx},{cy}): mean={crop.mean():.1f} std={crop.std():.1f}")

# Let's go with (20,340) - it has good edge content and shows the road
# But let's also try a crop that captures the lane divider + road
# Let's visualize the full image with a grid to pick the best road crop
img_vis = img2.copy()
from PIL import ImageDraw
draw = ImageDraw.Draw(img_vis)
# Draw the chosen crop location
cx, cy = 20, 340
draw.rectangle([cx, cy, cx+32, cy+32], outline='red', width=3)
img_vis.save('context/chosen_crop_location.png')
print(f"Chosen crop location (20,340) visualized")

# Print the full 32x32 grayscale crop
crop = arr[cy:cy+32, cx:cx+32]
print("\n32x32 grayscale crop:")
for row in crop:
    print(' '.join(f'{v:3d}' for v in row))