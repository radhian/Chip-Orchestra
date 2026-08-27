import subprocess, os
os.chdir('golden')
r = subprocess.run(['python','-m','pytest','tests','-q'], capture_output=True, text=True)
print("RC", r.returncode)
print("STDOUT", r.stdout[-3000:])
print("STDERR", r.stderr[-2000:])