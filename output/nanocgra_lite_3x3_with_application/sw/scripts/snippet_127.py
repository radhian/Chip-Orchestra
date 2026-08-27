import json, os

# Look at the kept vectors for the tricky modules to understand the timing model
for mod in ['baud_gen','uart_rx','uart_tx']:
    path = f'tb/vecs/{mod}_vecs.txt'
    with open(path) as f:
        lines = f.readlines()
    print(f"=== {mod} ({len(lines)-3} vecs) ===")
    for ln in lines[3:]:
        print(ln.rstrip())
    print()