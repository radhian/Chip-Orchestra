with open('waves/chip_output.mem') as f:
    lines = f.readlines()
vals = [int(l.strip(),16) for l in lines if l.strip() and not l.startswith('//')]
print("chip vals count:", len(vals))
print("first 30:", [hex(x) for x in vals[:30]])

with open('waves/golden_output.mem') as f:
    glines = f.readlines()
gvals = [int(l.strip(),16) for l in glines if l.strip() and not l.startswith('//')]
print("golden vals count:", len(gvals))
print("first 30:", [hex(x) for x in gvals[:30]])

# Check: do even-indexed chip vals match golden?
match_even = all(vals[i] == gvals[i] for i in range(0, min(len(vals),len(gvals)), 2))
print("even idx match:", match_even)
# Check odd
odd_mismatch = [(i, hex(vals[i]), hex(gvals[i])) for i in range(1, min(len(vals),len(gvals)), 2) if vals[i] != gvals[i]]
print("odd mismatches (first 10):", odd_mismatch[:10])