import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
flat = [p for row in g['pixels'] for p in row]
# Read the mem file
with open('rtl/sobel_input.mem') as f:
    mem = [int(line.strip(),16) for line in f if line.strip()]
print("mem len", len(mem), "first 10 mem:", mem[:10])
print("json first 10:", flat[:10])
print("match?", mem == flat)