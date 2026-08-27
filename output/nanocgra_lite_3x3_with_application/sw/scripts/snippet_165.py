import json, os

# Generate all unit testbenches from JSON vectors.
# For each module, we:
# 1. Read the JSON vectors
# 2. Generate a Verilog TB that instantiates the DUT, drives inputs, checks outputs
# 3. Bake the vectors as literals in the TB

# The timing model:
# - Sequential modules: drive inputs before posedge, check after posedge
# - Combinational modules: drive inputs, #1, check
# - For modules with clk: use a clock generator
# - For modules without clk (sobel_core): pure combinational

# Special handling:
# - baud_gen: 1309 vectors, check baud_tick at each cycle
# - uart_rx: 17365 vectors, drive rx_in, check rx_valid/rx_byte
# - uart_tx: 20853 vectors, need reconstructed stimulus (reset + tx_start pulses)
# - line_buffer: 39 vectors, row_out is 256-bit packed
# - window_3x3: 15 vectors, win is 72-bit packed
# - nano_controller: 7 vectors, check all outputs + state (internal)

# For large vector counts (baud_gen, uart_rx, uart_tx), we use $readmemh files
# to avoid huge TB files. For smaller ones, we bake as literals.

# Let's generate $readmemh files for the large ones and literals for small ones.

os.makedirs('tb/vecs', exist_ok=True)

def write_mem_file(path, data, width):
    """Write a .mem file with hex values."""
    with open(path, 'w') as f:
        for v in data:
            if width <= 4:
                f.write(f"{v:x}\n")
            else:
                f.write(f"{v:0{(width+3)//4}x}\n")

# Generate baud_gen TB data
# baud_gen: 1309 vectors, all with clk=1, rst_n=1 (except last few)
# We need to check baud_tick at each cycle.
# The TB: drive clk, rst_n, check baud_tick after each posedge.
# Vectors: first 1302 have rst_n=1, then some with rst_n=0.
with open('golden/vectors/baud_gen.json') as f:
    bg_data = json.load(f)

# Extract rst_n and expected baud_tick for each vector
bg_rst = [v['inputs']['rst_n'] for v in bg_data['vectors']]
bg_exp = [v['expected']['baud_tick'] for v in bg_data['vectors']]

# Write rst_n and expected as mem files
write_mem_file('tb/vecs/baud_rst.mem', bg_rst, 1)
write_mem_file('tb/vecs/baud_exp.mem', bg_exp, 1)
print(f"baud_gen: {len(bg_exp)} vectors written to mem files")

# Generate uart_rx TB data
with open('golden/vectors/uart_rx.json') as f:
    rx_data = json.load(f)

rx_in = [v['inputs']['rx_in'] for v in rx_data['vectors']]
rx_rst = [v['inputs']['rst_n'] for v in rx_data['vectors']]
# For expected: rx_valid is present in every vector, rx_byte only in some
rx_exp_valid = [v['expected'].get('rx_valid', 0) for v in rx_data['vectors']]
# rx_byte: use -1 when not present (meaning "don't check")
rx_exp_byte = [v['expected'].get('rx_byte', -1) for v in rx_data['vectors']]

write_mem_file('tb/vecs/uart_rx_in.mem', rx_in, 1)
write_mem_file('tb/vecs/uart_rx_rst.mem', rx_rst, 1)
write_mem_file('tb/vecs/uart_rx_exp_valid.mem', rx_exp_valid, 1)
# For rx_byte, use 0 when not checked, and a separate mask
rx_byte_mask = [1 if b >= 0 else 0 for b in rx_exp_byte]
rx_byte_val = [max(b, 0) for b in rx_exp_byte]
write_mem_file('tb/vecs/uart_rx_exp_byte.mem', rx_byte_val, 8)
write_mem_file('tb/vecs/uart_rx_byte_mask.mem', rx_byte_mask, 1)
print(f"uart_rx: {len(rx_exp_valid)} vectors written to mem files")

# Generate uart_tx TB data
with open('golden/vectors/uart_tx.json') as f:
    tx_data = json.load(f)

# Reconstructed stimulus:
# Frame 1: 3 warmup before vec 0 (tx_start=1 at warmup -3, data=60)
# Frame 2: reset at 5209, tx_start=1 at 5210, data=255
# Frame 3: reset at 10422, tx_start=1 at 10423, data=165
# Frame 4: reset at 15635, tx_start=1 at 15636, data=0
# Final: rst_n=0 at 20852

N = len(tx_data['vectors'])
tx_rst = [1] * N  # default rst_n=1
tx_start = [0] * N  # default tx_start=0
tx_data_in = [0] * N  # default data_in=0

# Final reset
tx_rst[20852] = 0

# Frame 2: reset at 5209, tx_start at 5210
tx_rst[5209] = 0
tx_start[5210] = 1
tx_data_in[5210] = 255

# Frame 3: reset at 10422, tx_start at 10423
tx_rst[10422] = 0
tx_start[10423] = 1
tx_data_in[10423] = 165

# Frame 4: reset at 15635, tx_start at 15636
tx_rst[15635] = 0
tx_start[15636] = 1
tx_data_in[15636] = 0

# Expected outputs
tx_exp_out = [v['expected'].get('tx_out', 1) for v in tx_data['vectors']]
tx_exp_done = [v['expected'].get('tx_done', 0) for v in tx_data['vectors']]

write_mem_file('tb/vecs/uart_tx_rst.mem', tx_rst, 1)
write_mem_file('tb/vecs/uart_tx_start.mem', tx_start, 1)
write_mem_file('tb/vecs/uart_tx_data.mem', tx_data_in, 8)
write_mem_file('tb/vecs/uart_tx_exp_out.mem', tx_exp_out, 1)
write_mem_file('tb/vecs/uart_tx_exp_done.mem', tx_exp_done, 1)
print(f"uart_tx: {N} vectors written to mem files")

# For frame 1 warmup: the TB will handle this with initial setup (3 warmup cycles
# before the vector loop, with tx_start=1 and data_in=60)