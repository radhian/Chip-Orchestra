import os

# Verify all required testbenches exist
required = [
    'tb/baud_gen_tb.v',
    'tb/cgra_3x3_tb.v',
    'tb/line_buffer_tb.v',
    'tb/mmio_bus_tb.v',
    'tb/nano_controller_tb.v',
    'tb/pe_tb.v',
    'tb/reset_sync_tb.v',
    'tb/sobel_core_tb.v',
    'tb/sram_32b_tb.v',
    'tb/uart_rx_tb.v',
    'tb/uart_tx_tb.v',
    'tb/window_3x3_tb.v',
    'tb/params_tb.v',
    'tb/nano_cgra_3x3_sobel_accelerator_v4_tb.v',
]

all_ok = True
for tb in required:
    if os.path.exists(tb):
        size = os.path.getsize(tb)
        print(f"  OK  {tb} ({size} bytes)")
    else:
        print(f"  MISSING  {tb}")
        all_ok = False

# Verify mem files exist
mem_files = [
    'tb/vecs/baud_rst.mem', 'tb/vecs/baud_exp.mem',
    'tb/vecs/uart_rx_in.mem', 'tb/vecs/uart_rx_rst.mem',
    'tb/vecs/uart_rx_exp_valid.mem', 'tb/vecs/uart_rx_exp_byte.mem',
    'tb/vecs/uart_rx_byte_mask.mem',
    'tb/vecs/uart_tx_rst.mem', 'tb/vecs/uart_tx_start.mem',
    'tb/vecs/uart_tx_data.mem', 'tb/vecs/uart_tx_exp_out.mem',
    'tb/vecs/uart_tx_exp_done.mem',
]
for mf in mem_files:
    if os.path.exists(mf):
        lines = sum(1 for _ in open(mf))
        print(f"  OK  {mf} ({lines} lines)")
    else:
        print(f"  MISSING  {mf}")
        all_ok = False

print(f"\nAll files present: {all_ok}")