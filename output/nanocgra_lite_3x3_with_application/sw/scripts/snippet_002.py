from PIL import Image
import numpy as np

# Look at the architecture image - crop and save sections to understand the CGRA diagram
img = Image.open('context/uploads/Screenshot_from_2026-08-01_19-42-51.png')
print("Architecture image size:", img.size)

# The data image - find the road region for 32x32 crop
img2 = Image.open('context/uploads/Screenshot_from_2026-07-14_16-24-31.png')
print("Data image size:", img2.size)
arr = np.array(img2.convert('L'))
print("Grayscale shape:", arr.shape)
print("Min/Max:", arr.min(), arr.max())

# Road is in bottom ~70% of frame (y > 360 in 1080, but image is 535 tall)
# Scale: 535/1080 = 0.495, so y > 360*0.495 = 178
# Road region: y from 178 to 535, x from 0 to ~700 (scaled from 1200)
# Let's find a good 32x32 crop showing the road with vehicles
# Red SUV at [0,540]-[96,680] in 1080 coords -> scaled: y 267-336, x 0-47
# Black car at [312,557]-[350,605] -> y 275-299, x 154-173
# White car at [426,563]-[459,589] -> y 278-291, x 210-226

# A 32x32 crop at x=150, y=270 would capture the road with cars (black and white car area)
# Let's check a few candidate crops
for (cx, cy) in [(150, 270), (100, 280), (50, 300), (200, 270)]:
    crop = arr[cy:cy+32, cx:cx+32]
    print(f"Crop at ({cx},{cy}): mean={crop.mean():.1f}, std={crop.std():.1f}, min={crop.min()}, max={crop.max()}")