from pathlib import Path
import re
src = Path('nanocgra_lite_3x3_opt_layout_lvs.spice')
out = Path('nanocgra_lite_3x3_opt_layout_lvs_norm.spice')
s = src.read_text()
s = s.replace('PHY_9/VDD', 'vdd')
s = s.replace('VSUBS', 'vss')
for i in range(64):
    s = s.replace(f'vdd_uq{i}', 'vdd')
    s = s.replace(f'vss_uq{i}', 'vss')
s = re.sub(r'\S+/VNW\b', 'vdd', s)
s = re.sub(r'\S+/VPW\b', 'vss', s)
out.write_text(s)
