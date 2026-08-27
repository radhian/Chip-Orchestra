import subprocess, sys
r = subprocess.run([sys.executable, '-m', 'pytest', 'golden/tests', '-q'], capture_output=True, text=True)
print("STDOUT:", r.stdout[-3000:])
print("STDERR:", r.stderr[-2000:])