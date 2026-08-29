import re
from pathlib import Path

vpath = Path('../../pnr/nanocgra_lite_3x3_opt.pnr.pwr.v')
stdpath = Path('stdcells_from_layout.spice')
out = Path('nanocgra_lite_3x3_opt_source_lvs.spice')

text = vpath.read_text()
std = stdpath.read_text()

subckt_pins = {}
for m in re.finditer(r'^\.subckt\s+(\S+)\s+(.+)$', std, re.M):
    subckt_pins[m.group(1)] = m.group(2).split()

parent = {}
def find(x):
    parent.setdefault(x, x)
    if parent[x] != x:
        parent[x] = find(parent[x])
    return parent[x]
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        keep = min(ra, rb, key=lambda s: (len(s), s))
        other = rb if keep == ra else ra
        parent[other] = keep

def norm(n):
    n = n.strip()
    if not n:
        return n
    if n.startswith('\\'):
        n = n[1:].strip()
    if n in ("1'b0", "1'h0", "1'd0", "0"):
        return 'vss'
    if n in ("1'b1", "1'h1", "1'd1", "1"):
        return 'vdd'
    return re.sub(r'[^A-Za-z0-9_./\[\]-]', '_', n)

for a, b in re.findall(r'assign\s+([^=;]+?)\s*=\s*([^;]+?)\s*;', text, re.S):
    union(norm(a), norm(b))

ports_m = re.search(r'module\s+NanoCGRA_Lite\s*\((.*?)\);', text, re.S)
ports = [norm(p) for p in re.findall(r'\\[^\s,()]+\s?|[A-Za-z_][A-Za-z0-9_$]*', ports_m.group(1))]
# Keep D04/reference order to match layout extraction.
ports = ['vss','clk_PU','clk_PD','clk','rst_n_PU','rst_n_PD','rst_n','uart_rx_PU','uart_rx_PD','uart_rx','uart_tx_CS','uart_tx_SL','uart_tx_IE','uart_tx_OE','uart_tx_PU','uart_tx_PD','uart_tx_OUT','uart_tx_IN','vdd']

inst_re = re.compile(r'\b(gf180mcu_fd_sc_mcu7t5v0__[A-Za-z0-9_]+)\s+(\\[^\s(]+|[A-Za-z0-9_$./\[\]-]+)\s*\((.*?)\);', re.S)
conn_re = re.compile(r'\.([A-Za-z0-9_]+)\s*\(\s*([^()]+?)\s*\)', re.S)
lines = ['* Source LVS SPICE generated from post-route power Verilog', '.subckt NanoCGRA_Lite ' + ' '.join(ports)]
missing = set()
count = 0
for cell, inst, body in inst_re.findall(text):
    pins = subckt_pins.get(cell)
    if not pins:
        missing.add(cell)
        continue
    conns = {p: norm(n) for p, n in conn_re.findall(body)}
    ordered = []
    for p in pins:
        if p in conns:
            ordered.append(find(conns[p]))
        elif p in ('VDD','VNW'):
            ordered.append('vdd')
        elif p in ('VSS','VPW'):
            ordered.append('vss')
        else:
            ordered.append(f'{norm(inst)}/{p}')
    lines.append('X' + norm(inst) + ' ' + ' '.join(ordered) + ' ' + cell)
    count += 1
lines += ['.ends NanoCGRA_Lite', '']
out.write_text('\n'.join(lines))
print(f'wrote {out} instances={count} missing={sorted(missing)}')
