# Read chip_output.mem and golden_output.mem
with open('waves/chip_output.mem') as f:
    chip = [int(x,16) for x in f.read().split()]
with open('waves/golden_output.mem') as f:
    golden = [int(x,16) for x in f.read().split()]
print("chip first 12:", [hex(x) for x in chip[:12]])
print("golden first 12:", [hex(x) for x in golden[:12]])
print("chip len", len(chip), "golden len", len(golden))

# Check the difference pattern
for i in range(12):
    print(f"i={i} chip={hex(chip[i])} golden={hex(golden[i])} diff={chip[i]-golden[i]}")