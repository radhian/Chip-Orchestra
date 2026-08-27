import json, os
path = os.path.join('context', 'chip_input_grid.json')
with open(path) as f:
    data = json.load(f)
pixels_2d = data['pixels']
# Print first 4 rows x 5 cols
for r in range(4):
    print(f"row {r}: {pixels_2d[r][:6]}")
print(f"grid size: {len(pixels_2d)}x{len(pixels_2d[0])}")