import subprocess
result = subprocess.run(['sh','-c','iverilog -g2012 -o work/re.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4_tb rtl/*.v tb/nano_cgra_3x3_sobel_accelerator_v4_tb.* && vvp work/re.vvp'], capture_output=True, text=True, timeout=600)
print("STDOUT (last 3000):", result.stdout[-3000:])
print("STDERR (last 1000):", result.stderr[-1000:])
print("RC:", result.returncode)