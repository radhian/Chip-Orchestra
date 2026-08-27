import json, os, re

# Helper: emit a Verilog literal for a value of given width
def vlit(v, w):
    if w == 1:
        return f"1'b{v & 1}"
    return f"{w}'h{v & ((1<<w)-1):0{(w+3)//4}x}"

# We will generate testbenches that:
#  - instantiate the DUT
#  - drive a clock
#  - for each vector: set inputs, pulse clock (posedge), check outputs
# The golden model step() is called with clk=1 each cycle and returns post-edge outputs.
# So in the TB: set inputs @(negedge clk); @(posedge clk) #1; check outputs.

# For combinational modules (sobel_core, pe, mmio_bus, window_3x3 win output),
# the golden model returns the value in the SAME step (combinational). But the
# golden vectors still list them per-cycle. For combinational-only modules
# (sobel_core has no clk/rst_n), we just set inputs and check after a delay.

# Let's classify modules by whether they have clk+rst_n (sequential) or not.
# sobel_core: inputs=[win], no clk/rst_n -> purely combinational
# pe: has clk, rst_n but combinational always@(*) -> check after setting inputs + small delay
# mmio_bus: combinational always@(*)
# window_3x3: win is combinational assign, window_valid combinational; shift regs sequential
# line_buffer: row_out is combinational (always@(*)) but mem is sequential
# reset_sync: sequential
# baud_gen: sequential
# sram_32b: sequential (data_out registered)
# nano_controller: sequential
# uart_rx/uart_tx: sequential

# For sequential modules: drive inputs at negedge, posedge, then check.
# For combinational modules: drive inputs, #1, check (no clock needed but we
# still provide clk for instantiation compatibility).

# Let's check which modules have clk in inputs
for fn in sorted(os.listdir('golden/vectors')):
    if not fn.endswith('.json'): continue
    with open(os.path.join('golden/vectors', fn)) as f:
        data = json.load(f)
    ins = [o[0] for o in data['ports']['inputs']]
    print(f"{data['module']:40s} inputs={ins}")