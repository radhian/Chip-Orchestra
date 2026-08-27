import sys
sys.path.insert(0, '.')

from golden.model.baud_gen import BaudGen
from golden.model.uart_tx import UartTx

# Read the input mem files
with open('tb/vecs/uart_tx_rst.mem') as f:
    v_rst = [int(line.strip()) for line in f if line.strip()]
with open('tb/vecs/uart_tx_start.mem') as f:
    v_tx_start = [int(line.strip()) for line in f if line.strip()]
with open('tb/vecs/uart_tx_data.mem') as f:
    v_data_in = [int(line.strip(), 16) for line in f if line.strip()]

print(f"Vector count: rst={len(v_rst)}, start={len(v_tx_start)}, data={len(v_data_in)}")

# Simulate the testbench
tx = UartTx()
tx.reset()

# Warmup: 3 cycles with rst_n=1, tx_start=1, data_in=60
tx.step(1, 1, 1, 60)  # warmup -3
tx.step(1, 1, 0, 60)  # warmup -2
tx.step(1, 1, 0, 60)  # warmup -1

# Run 20853 vectors
exp_out = []
exp_done = []

for i in range(20853):
    rst_n = v_rst[i]
    tx_start = v_tx_start[i]
    data_in = v_data_in[i]
    tx_out, tx_done = tx.step(1, rst_n, tx_start, data_in)
    exp_out.append(tx_out)
    exp_done.append(tx_done)

# Write the expected output files
with open('tb/vecs/uart_tx_exp_out.mem', 'w') as f:
    for v in exp_out:
        f.write(f"{v}\n")
with open('tb/vecs/uart_tx_exp_done.mem', 'w') as f:
    for v in exp_done:
        f.write(f"{v}\n")

print("Vectors regenerated")

# Check: how many tx_done pulses?
done_count = sum(exp_done)
print(f"tx_done pulses: {done_count}")

# Find the done pulse positions
done_positions = [i for i, d in enumerate(exp_done) if d]
print(f"Done positions: {done_positions}")