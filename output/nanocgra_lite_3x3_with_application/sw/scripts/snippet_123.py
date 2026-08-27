import json, os

# Parse all JSON vector files and summarize
vecs_dir = 'golden/vectors'
for fn in sorted(os.listdir(vecs_dir)):
    if not fn.endswith('.json'): continue
    path = os.path.join(vecs_dir, fn)
    with open(path) as f:
        data = json.load(f)
    mod = data['module']
    nv = len(data['vectors'])
    # Find non-default outputs
    outs = [o[0] for o in data['ports']['outputs']]
    interesting = 0
    for v in data['vectors']:
        exp = v['expected']
        # count vectors where any output is non-zero/non-default
        if any(exp.get(o,0) != 0 for o in outs):
            interesting += 1
    print(f"{mod:40s} vectors={nv:8d} interesting={interesting:6d} outputs={outs}")