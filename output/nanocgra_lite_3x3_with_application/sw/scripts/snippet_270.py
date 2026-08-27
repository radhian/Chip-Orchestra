import json
# Check if sobel_input.mem matches chip_input_grid.json
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels = grid['pixels']
flat = [p for row in pixels for p in row]
print("chip_input_grid flat first 32:", flat[:32])
print("chip_input_grid flat len:", len(flat))

# Read sobel_input.mem
with open('rtl/sobel_input.mem') as f:
    mem = [int(line.strip(),16) for line in f if line.strip()]
print("sobel_input.mem first 32:", mem[:32])
print("sobel_input.mem len:", len(mem))

# Compare
match = all(flat[i]==mem[i] for i in range(len(flat)))
print("MATCH:", match)
if not match:
    for i in range(len(flat)):
        if flat[i]!=mem[i]:
            print(f"  diff at {i}: grid={flat[i]} mem={mem[i]}")
            if i>5: break