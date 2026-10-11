"""Independent readback of top-level metal/via connectivity, not device LVS."""
from pathlib import Path
import json,sys
import gdstk
HERE=Path(__file__).resolve().parent
ws=HERE/'combined_padframe'
if '--probe' in sys.argv:ws=ws/'probe'
gds=ws/'padring/ChipOrchestraDualCore_chip.gds'
lib=gdstk.read_gds(str(gds))
top=next(c for c in lib.cells if c.name=='ChipOrchestraDualCore_chip')
report=json.loads((ws/'padring/pin_assembly_report.json').read_text())
metal={2:36,3:42,4:46,5:81}
cut={2:38,3:40,4:41}
components={}
parent=[]
def find(i):
 while parent[i]!=i:
  parent[i]=parent[parent[i]];i=parent[i]
 return i
def join(a,b):parent[find(b)]=find(a)
for level,layer in metal.items():
 shapes=[p for p in top.polygons if p.layer==layer]
 united=gdstk.boolean(shapes,[],'or',precision=0.001)
 entries=[]
 for p in united:
  index=len(parent);parent.append(index);entries.append((index,p))
 components[level]=entries
def locate(level,point):
 return [i for i,p in components[level] if gdstk.inside([point],[p])[0]]
vias=0
for level,layer in cut.items():
 for via in [p for p in top.polygons if p.layer==layer]:
  box=via.bounding_box();point=((box[0][0]+box[1][0])/2,(box[0][1]+box[1][1])/2)
  below,above=locate(level,point),locate(level+1,point)
  assert below and above,f'Orphan via at {point}, layer {layer}'
  for a in below:
   for b in above:join(a,b)
  vias+=1
roots={}
power_roots={}
for label in top.labels:
 if not label.text.startswith(('PORT::','PGPORT::')):continue
 kind,net,terminal=label.text.split('::')
 level=next(k for k,v in metal.items() if v==label.layer)
 nodes=locate(level,label.origin)
 assert nodes,f'Label is disconnected from metal: {label.text}'
 target=roots if kind=='PORT' else power_roots
 target.setdefault(net,{})[terminal]=find(nodes[0])
assert len(roots)==9
assert all(v['pad']==v['core'] for v in roots.values()),roots
assert len({v['pad'] for v in roots.values()})==9,'Shorted signal nets'
assert len(power_roots)==4 and all(v['pad']==v['core'] for v in power_roots.values()),power_roots
assert not {v['pad'] for v in roots.values()} & {v['pad'] for v in power_roots.values()},'Signal short to power'
assert not {v['pad'] for n,v in power_roots.items() if n.endswith('/VDD')} & {v['pad'] for n,v in power_roots.items() if n.endswith('/VSS')},'Power-ground short'
# Check the readback endpoints against actual referenced pad/core geometry.
ring=next(r.cell for r in top.references if r.cell.name=='RING_PAD')
for connection in report['connections']:
 pad=ring.references[connection['pad_reference']]
 assert gdstk.inside([connection['pad_point_um']],pad.get_polygons(layer=36,datatype=0))[0]
 core=next(r for r in top.references if r.cell.name.startswith(connection['core']+'__'))
 layer=report['stream_layers'][connection['core_layer']]
 assert gdstk.inside([connection['core_point_um']],core.get_polygons(layer=layer,datatype=0))[0]
for connection in report['power_connections']:
 pad=ring.references[connection['pad_reference']]
 assert gdstk.inside([connection['pad_rail_point_um']],pad.get_polygons(layer=42,datatype=0))[0]
 core=next(r for r in top.references if r.cell.name.startswith(connection['core']+'__'))
 assert gdstk.inside([connection['core_point_um']],core.get_polygons(layer=46,datatype=0))[0]
result={'gds':str(gds),'independent_signal_connections_verified':9,'signal_shorts':0,'orphan_vias':0,'top_level_vias_checked':vias,
        'independent_power_connections_verified':4,
        'actual_pad_and_core_endpoint_overlap':True,'scope':'Top-level metal/via extraction plus actual referenced pin overlap, not full-chip device LVS'}
(ws/'reports/gds_connectivity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
