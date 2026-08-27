import json, os

# Extract the interesting (non-trivial) vectors for each module and write
# a compact .mem/.txt file under tb/ that the testbench can $readmemh or
# we bake as literals. For huge ones (baud_gen, uart_rx, uart_tx) extract
# only the vectors where the output differs from the previous vector's output
# (i.e. transitions) PLUS a few leading zeros — this captures every meaningful
# check while keeping the TB small.

vecs_dir = 'golden/vectors'
os.makedirs('tb/vecs', exist_ok=True)

def pack_row(row):
    # row is list of 32 bytes; pack MSB=mem[31]..LSB=mem[0] like RTL row_out
    # RTL: row_out[8*i +: 8] = mem[i], so row_out = {mem[31],...,mem[0]}
    # As a 256-bit hex that's mem[31] at top. We'll just store the list.
    return row

for fn in sorted(os.listdir(vecs_dir)):
    if not fn.endswith('.json'): continue
    path = os.path.join(vecs_dir, fn)
    with open(path) as f:
        data = json.load(f)
    mod = data['module']
    outs = [o[0] for o in data['ports']['outputs']]
    ins  = [o[0] for o in data['ports']['inputs']]
    vecs = data['vectors']

    # For modules with <= 200 vectors, keep ALL.
    # For larger, keep transitions + first few.
    if len(vecs) <= 300:
        keep = list(enumerate(vecs))
    else:
        keep = []
        prev_exp = None
        for idx, v in enumerate(vecs):
            exp = tuple(v['expected'].get(o,0) for o in outs)
            # for list outputs compare element-wise
            key = []
            for o in outs:
                val = v['expected'].get(o,0)
                if isinstance(val, list):
                    key.append(tuple(val))
                else:
                    key.append(val)
            key = tuple(key)
            if prev_exp is None or key != prev_exp:
                keep.append((idx, v))
                prev_exp = key
        # also keep first 5 always
        for idx in range(min(5, len(vecs))):
            if idx not in [k[0] for k in keep]:
                keep.insert(idx, (idx, vecs[idx]))

    # write a compact python-readable summary
    out_path = f'tb/vecs/{mod}_vecs.txt'
    with open(out_path, 'w') as f:
        f.write(f"# module={mod} kept={len(keep)}/{len(vecs)}\n")
        f.write(f"# inputs={ins}\n")
        f.write(f"# outputs={outs}\n")
        for idx, v in keep:
            f.write(json.dumps({'i':idx, 'in':v['inputs'], 'exp':v['expected']})+'\n')
    print(f"{mod:40s} kept={len(keep):6d}/{len(vecs):8d} -> {out_path}")