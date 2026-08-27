import subprocess
# Try yosys synthesis
r = subprocess.run(['sh','-c','yosys -p "read_verilog -Irtl rtl/*.v; synth -top nano_cgra_3x3_sobel_accelerator_v4" 2>&1 | tail -80'], capture_output=True, text=True)
print(r.stdout[-5000:])
print("STDERR:", r.stderr[-2000:])