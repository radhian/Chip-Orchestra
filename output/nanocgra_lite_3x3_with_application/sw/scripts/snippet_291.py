import subprocess
# Try iverilog with stricter synthesis-like flags
r = subprocess.run(['sh','-c','iverilog -g2012 -Wall -o /tmp/lint.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4 rtl/*.v 2>&1 | head -80'], capture_output=True, text=True)
print("IVERILOG -Wall:", r.stdout[-4000:])