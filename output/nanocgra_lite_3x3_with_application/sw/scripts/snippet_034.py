import json, os
p = os.path.join('context','chip_input_grid.json')
with open(p) as f: data = json.load(f)
px = data['pixels']
print('rows', len(px), 'cols', len(px[0]))
# print first 3 rows
for r in range(3):
    print(px[r])