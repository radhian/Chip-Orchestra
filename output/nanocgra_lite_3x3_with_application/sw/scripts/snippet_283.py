import subprocess
r = subprocess.run(['sh','-c','iverilog -g2012 -o work/re.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4_tb rtl/*.v tb/nano_cgra_3x3_sobel_accelerator_v4_tb.* && vvp work/re.vvp'], capture_output=True, text=True)
print("STDOUT (last 3000):", r.stdout[-3000:])
print("STDERR (last 2000):", r.stderr[-2000:])
print("RC:", r.returncode)