import subprocess

# Run the simulation
cmd = ['vvp', 'sim.out']
print("Running simulation...")
result = subprocess.run(cmd, capture_output=True, text=True, cwd='.', timeout=120)
print("STDOUT:", result.stdout[-3000:])
print("STDERR:", result.stderr[-1000:])
print("RC:", result.returncode)