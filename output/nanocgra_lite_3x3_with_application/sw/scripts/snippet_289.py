import subprocess
# Check what synthesis tools are available
r = subprocess.run(['sh','-c','which yosys verilator nextpnr 2>&1; ls /opt 2>&1; ls /usr/local/bin 2>&1 | head -30'], capture_output=True, text=True)
print(r.stdout)