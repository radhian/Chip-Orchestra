import re
def load_mem(path):
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            for tok in line.split():
                if tok.startswith('//'): break
                vals.append(int(tok, 16))
    return vals

chip = load_mem('waves/chip_output.mem')
golden = load_mem('waves/golden_output.mem')
print("chip first 12:", [hex(x) for x in chip[:12]])
print("golden first 12:", [hex(x) for x in golden[:12]])
print("chip len", len(chip), "golden len", len(golden))
for i in range(20):
    print(f"i={i} chip={hex(chip[i])} golden={hex(golden[i])} diff={chip[i]-golden[i]}")