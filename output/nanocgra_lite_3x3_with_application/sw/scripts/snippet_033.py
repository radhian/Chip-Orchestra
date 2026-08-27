import subprocess, sys
r = subprocess.run([sys.executable,'-m','pytest','golden/tests','-q'], capture_output=True, text=True)
print("STDOUT (tail 3000):")
print(r.stdout[-3000:])
print("STDERR (tail 1500):")
print(r.stderr[-1500:])