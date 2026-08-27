import json

# Read the input grid and golden output
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)

with open('waves/golden_output.mem') as f:
    golden = [int(line.strip(), 16) for line in f if line.strip()]

print(f"Input: {grid['N']}x{grid['N']} = {len(grid['pixels'])} pixels")
print(f"Golden output: {len(golden)} values (expected {30*30}={30*30})")
print(f"First 10 input pixels: {grid['pixels'][0][:10]}")
print(f"First 10 golden outputs: {golden[:10]}")
print(f"Golden output range: {min(golden)}..{max(golden)}")

# Read the sobel_input.mem to verify it matches the grid
with open('rtl/sobel_input.mem') as f:
    mem_input = [int(line.strip(), 16) for line in f if line.strip()]
print(f"\nsobel_input.mem: {len(mem_input)} values")
print(f"First 10: {mem_input[:10]}")
print(f"Grid first 10: {grid['pixels'][0][:10]}")
print(f"Match: {mem_input[:10] == grid['pixels'][0][:10]}")

# Check if sobel_input.mem is the flat pixel array
flat_pixels = [p for row in grid['pixels'] for p in row]
print(f"Full match: {mem_input == flat_pixels}")