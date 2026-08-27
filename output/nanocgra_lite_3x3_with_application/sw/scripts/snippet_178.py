import json
with open('waves/golden_output.mem') as f:
    gmem = [int(line.strip(),16) for line in f if line.strip()]
with open('context/golden_ref.json') as f:
    gref = json.load(f)
print("gmem len", len(gmem), "gref len", len(gref))
print("gmem first 10:", gmem[:10])
print("gref first 10:", gref[:10])
print("match?", [int(x) for x in gmem] == gref)