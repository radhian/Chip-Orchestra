from PIL import Image
img = Image.open('context/uploads/Screenshot_from_2026-08-01_19-42-51.png')
print("Architecture image size:", img.size)
img2 = Image.open('context/uploads/Screenshot_from_2026-07-14_16-24-31.png')
print("Data image size:", img2.size)