import json
# Load canonical input
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = grid['pixels']
flat = [p for row in pixels for p in row]
print("N=", grid['N'], "flat len=", len(flat))
print("first 5:", flat[:5])
# Compare with rtl/sobel_input.mem
with open('rtl/sobel_input.mem') as f:
    mem = [int(line.strip(),16) for line in f if line.strip()]
print("mem len=", len(mem), "first 5:", mem[:5])
print("match:", flat == mem)