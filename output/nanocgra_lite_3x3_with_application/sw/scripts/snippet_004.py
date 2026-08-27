from PIL import Image
import numpy as np

img2 = Image.open('context/uploads/Screenshot_from_2026-07-14_16-24-31.png')
arr = np.array(img2.convert('L'))

# Let's look at crops that show the road with vehicles - the red SUV area and lane markings
# Red SUV at scaled [0,267]-[47,336], let's try a crop that captures the road with the red SUV and lane lines
# (20,340) has good std and low mean (55) - likely road with dark vehicles
# Let's also check around the lane divider area

# Let's visualize where these crops are on the original image
from PIL import ImageDraw
img_vis = img2.copy()
draw = ImageDraw.Draw(img_vis)
for i, (s, cx, cy, m) in enumerate([
    (54.0, 320, 390, 138.0),
    (53.8, 400, 300, 151.0),
    (52.3, 20, 340, 55.2),
    (52.0, 400, 290, 152.3),
]):
    draw.rectangle([cx, cy, cx+32, cy+32], outline='red', width=2)
    draw.text((cx, cy-10), f"#{i} std={s:.0f}", fill='red')
img_vis.save('context/crop_locations.png')
print("Saved crop locations visualization")

# The crop at (20,340) with mean=55 is likely the road with the red SUV - good edge content
# Let's verify by looking at the color content
crop_rgb = np.array(img2.crop((20, 340, 52, 372)))
print(f"Crop (20,340) RGB mean: R={crop_rgb[:,:,0].mean():.0f} G={crop_rgb[:,:,1].mean():.0f} B={crop_rgb[:,:,2].mean():.0f}")
print(f"Crop (20,340) shape: {crop_rgb.shape}")

# Let's also check (0,350) which might capture the red SUV
crop_rgb2 = np.array(img2.crop((0, 350, 32, 382)))
print(f"Crop (0,350) RGB mean: R={crop_rgb2[:,:,0].mean():.0f} G={crop_rgb2[:,:,1].mean():.0f} B={crop_rgb2[:,:,2].mean():.0f}")