import json, sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream

with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = grid['pixels']
flat = [p for row in pixels for p in row]

out = sobel_stream(flat)
chip = [0x64,0x84,0x0a,0x84,0x0c,0x86,0x0c,0x86,0x0c,0x88,0x10,0x88,0x14,0xe9,0xc0,0xe8,0x40,0x82,0x06,0x82,0x06]

# Check if chip is shifted version of golden
for shift in range(-5, 6):
    matches = 0
    for i in range(len(chip)):
        gi = i + shift
        if 0 <= gi < len(out) and out[gi] == chip[i]:
            matches += 1
    print(f"shift={shift}: matches={matches}/{len(chip)}")