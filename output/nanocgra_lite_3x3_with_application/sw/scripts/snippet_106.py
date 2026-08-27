import subprocess, os

# Compile all RTL files together with iverilog
rtl_files = [
    'rtl/params.vh',
    'rtl/reset_sync.v',
    'rtl/baud_gen.v',
    'rtl/uart_rx.v',
    'rtl/uart_tx.v',
    'rtl/line_buffer.v',
    'rtl/window_3x3.v',
    'rtl/pe.v',
    'rtl/sobel_core.v',
    'rtl/cgra_3x3.v',
    'rtl/sram_32b.v',
    'rtl/mmio_bus.v',
    'rtl/nano_controller.v',
    'rtl/nano_cgra_3x3_sobel_accelerator_v4.v',
]

tb_file = 'tb/nano_cgra_3x3_sobel_accelerator_v4_tb.v'

# Build iverilog command
cmd = ['iverilog', '-g2001', '-o', 'sim.out', '-I', 'rtl'] + rtl_files + [tb_file]
print("CMD:", ' '.join(cmd))
result = subprocess.run(cmd, capture_output=True, text=True, cwd='.')
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("RC:", result.returncode)