import subprocess
result = subprocess.run(['sh','-c','iverilog -g2012 -o work/re.vvp -Irtl -s nano_cgra_3x3_sobel_accelerator_v4_tb rtl/*.v tb/nano_cgra_3x3_sobel_accelerator_v4_tb.* && vvp work/re.vvp 2>&1 | head -50'], capture_output=True, text=True, shell=False)
print(result.stdout[:5000])