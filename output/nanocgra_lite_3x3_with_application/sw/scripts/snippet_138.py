import json
# Verify reset_sync, baud_gen, uart_rx, uart_tx vectors against golden model
import sys
sys.path.insert(0, 'golden')
from model.reset_sync import ResetSync
from model.baud_gen import BaudGen
from model.uart_rx import UartRx
from model.uart_tx import UartTx

for mod, cls, extra in [
    ('reset_sync', ResetSync, None),
    ('baud_gen', BaudGen, None),
    ('uart_rx', UartRx, None),
    ('uart_tx', UartTx, None),
]:
    with open(f'golden/vectors/{mod}.json') as f:
        data = json.load(f)
    m = cls()
    m.reset()
    mismatches = 0
    for i, v in enumerate(data['vectors']):
        inp = v['inputs']
        exp = v['expected']
        if mod == 'reset_sync':
            out = m.step(inp['clk'], inp['rst_async_n'])
            if out != exp['rst_n']:
                mismatches += 1
                if mismatches <= 3:
                    print(f"{mod} vec {i}: MISMATCH out={out} exp={exp}")
        elif mod == 'baud_gen':
            out = m.step(inp['clk'], inp['rst_n'])
            if out != exp['baud_tick']:
                mismatches += 1
                if mismatches <= 3:
                    print(f"{mod} vec {i}: MISMATCH out={out} exp={exp}")
        elif mod == 'uart_rx':
            byte, valid = m.step(inp['clk'], inp['rst_n'], inp['rx_in'])
            exp_valid = exp.get('rx_valid', 0)
            exp_byte = exp.get('rx_byte', None)
            if valid != exp_valid or (exp_byte is not None and byte != exp_byte):
                mismatches += 1
                if mismatches <= 5:
                    print(f"{mod} vec {i}: MISMATCH byte={byte} valid={valid} exp={exp}")
        elif mod == 'uart_tx':
            tx_out, tx_done = m.step(inp['clk'], inp['rst_n'], inp['tx_start'], inp['data_in'])
            exp_out = exp.get('tx_out', None)
            exp_done = exp.get('tx_done', None)
            if (exp_out is not None and tx_out != exp_out) or (exp_done is not None and tx_done != exp_done):
                mismatches += 1
                if mismatches <= 5:
                    print(f"{mod} vec {i}: MISMATCH tx_out={tx_out} tx_done={tx_done} exp={exp}")
    print(f"{mod}: {len(data['vectors'])} vectors, {mismatches} mismatches")