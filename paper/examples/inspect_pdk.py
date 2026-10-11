from pathlib import Path
import sys,re,json
import gdstk
root=Path(__file__).resolve().parents[2]
ring=root/'eda-service/toolchain/gf180/RING_PAD.gds'
lib=gdstk.read_gds(str(ring))
top=lib.top_level()[0]
print('RING',top.name,top.bounding_box())
for i,r in enumerate(top.references):
 name=r.cell.name
 if any(k in name for k in ('__in_c','__bi_t','__asig','__dvdd','__dvss')):
  print('REF',i,name,r.origin,r.rotation,r.x_reflection)
  print('LABELS',[(x.text,x.origin,x.layer,x.texttype) for x in r.cell.labels][:30])
pdk=Path('/home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_io/lef')
for p in pdk.glob('*.lef'):
 s=p.read_text()
 for cell in ['gf180mcu_fd_io__in_c','gf180mcu_fd_io__bi_t','gf180mcu_fd_io__asig_5p0','gf180mcu_fd_io__dvdd','gf180mcu_fd_io__dvss']:
  match=re.search(r'MACRO\s+'+cell+r'\b(.*?)END\s+'+cell+r'\b',s,re.S)
  if match:print(match.group(0))
