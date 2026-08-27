# Input matches. Let me check the golden_output.mem too.
import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]

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

golden_mem = load_mem('waves/golden_output.mem')

# Run golden sobel_stream
import sys
sys.path.insert(0, 'golden')
from model.top import sobel_stream
golden_stream = sobel_stream(pixels)

print("golden_mem first 12:", [hex(x) for x in golden_mem[:12]])
print("golden_stream first 12:", [hex(x) for x in golden_stream[:12]])
print("match:", golden_mem[:12] == golden_stream[:12])
print("full match:", golden_mem == golden_stream)