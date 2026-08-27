import json
# The vector file vec 37 shows [0,...,0,42] which is inconsistent with the golden model
# (which would keep [5..36] when shift_en=0). This is a discrepancy in the vector file.
# Let me check: maybe the vectors were generated with a DIFFERENT stimulus than the test.
# The vector file is the CONTRACT per the instructions. Let me re-run the golden model
# with the EXACT stimulus from the vector file to see what the model produces.

import sys
sys.path.insert(0, 'golden')
from model.line_buffer import LineBuffer

with open('golden/vectors/line_buffer.json') as f:
    data = json.load(f)

lb = LineBuffer()
lb.reset()
for i, v in enumerate(data['vectors']):
    inp = v['inputs']
    row = lb.step(inp['clk'], inp['rst_n'], inp['shift_en'], inp['pixel_in'])
    exp = v['expected']['row_out']
    match = row == exp
    if not match:
        print(f"vec {i}: MISMATCH model={row[:5]}..{row[-5:]} expected={exp[:5]}..{exp[-5:]}")
    else:
        print(f"vec {i}: OK")