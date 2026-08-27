import subprocess
# Try verilator for linting (it catches many synthesis issues)
r = subprocess.run(['sh','-c','verilator --lint-only -Wno-WIDTH -Wno-UNOPTFLAT -Wno-DECLFILENAME -Wno-UNUSED -Irtl --top-module nano_cgra_3x3_sobel_accelerator_v4 rtl/*.v 2>&1 | head -60'], capture_output=True, text=True)
print("VERILATOR:", r.stdout[-4000:])
print("STDERR:", r.stderr[-2000:])