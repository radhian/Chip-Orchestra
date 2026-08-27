import json
# The mismatches suggest the vector files were generated with a DIFFERENT timing model
# than the current golden model. The vectors are the CONTRACT regardless.
# Let me look at the reset_sync mismatch more carefully.
import sys
sys.path.insert(0, 'golden')
from model.reset_sync import ResetSync

with open('golden/vectors/reset_sync.json') as f:
    data = json.load(f)

m = ResetSync()
m.reset()
for i, v in enumerate(data['vectors']):
    inp = v['inputs']
    exp = v['expected']
    out = m.step(inp['clk'], inp['rst_async_n'])
    print(f"vec {i}: rst_async_n={inp['rst_async_n']} model_rst_n={out} exp_rst_n={exp['rst_n']} {'OK' if out==exp['rst_n'] else 'MISMATCH'}")