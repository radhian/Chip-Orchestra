import json
# Let me verify the nano_controller vectors against the golden model to understand timing
import sys
sys.path.insert(0, 'golden')
from model.nano_controller import NanoController

with open('golden/vectors/nano_controller.json') as f:
    data = json.load(f)

ctrl = NanoController()
ctrl.reset()
for i, v in enumerate(data['vectors']):
    inp = v['inputs']
    out = ctrl.step(inp['clk'], inp['rst_n'], inp['rx_byte'], inp['rx_valid'],
                    inp['tx_done'], inp['cgra_done'], inp['sobel_out'])
    exp = v['expected']
    # compare all keys except 'state' (which is internal)
    match = True
    for k in exp:
        if k == 'state': continue
        if out.get(k, 0) != exp[k]:
            match = False
            break
    print(f"vec {i}: {'OK' if match else 'MISMATCH'} out={out} exp={exp}")