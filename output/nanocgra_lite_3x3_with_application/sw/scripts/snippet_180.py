import json
with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/golden_ref.json') as f:
    gref = json.load(f)
print("chip len", len(cmem), "first 20 chip:", cmem[:20])
print("first 20 golden:", gref[:20])
# Check if chip is shifted by some offset
for off in range(-5, 6):
    c = cmem[max(0,off):max(0,off)+20]
    g = gref[max(0,off):max(0,off)+20]
    m = sum(1 for a,b in zip(c,g) if a==b)
    print(f"offset {off}: matches {m}/20")