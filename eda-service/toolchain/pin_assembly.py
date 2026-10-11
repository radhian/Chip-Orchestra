"""Explicit multi-core GF180 assembly using actual DEF and IO LEF pins.

Routes use the PDK stream map and via shapes, rather than drawing approximate
endpoints. This verifies assembly geometry, not foundry full-chip signoff.
"""
from pathlib import Path
from collections import Counter
import heapq,json,math,re

def stream_map(path):
    result={}
    for line in Path(path).read_text().splitlines():
        fields=line.split()
        if len(fields)>=4 and fields[0].startswith(('Metal','Via')) and fields[2].isdigit():
            if fields[3]=='0':result[fields[0]]=int(fields[2])
    return result

def def_pins(path):
    text=Path(path).read_text()
    dbu=int(re.search(r'UNITS DISTANCE MICRONS\s+(\d+)',text).group(1))
    section=re.search(r'\bPINS\s+\d+\s*;(.*?)END PINS',text,re.S).group(1)
    pins={}
    for entry in section.split(';'):
        name=re.search(r'^\s*-\s+(\S+)',entry)
        if not name:continue
        geometry=re.search(r'\+ LAYER\s+(\w+)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)',entry)
        placement=re.search(r'\+ (?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)',entry)
        if not geometry or not placement:raise ValueError(f'Pin lacks geometry: {name[1]}')
        if placement[3]!='N':raise ValueError(f'Unsupported DEF pin orientation: {placement[3]}')
        x,y=int(placement[1])/dbu,int(placement[2])/dbu
        v=[int(k)/dbu for k in geometry.groups()[1:]]
        pins[name[1]]={'layer':geometry[1],'point':(x+(v[0]+v[2])/2,y+(v[1]+v[3])/2),
                       'rect':(x+v[0],y+v[1],x+v[2],y+v[3]),
                       'direction':re.search(r'\+ DIRECTION\s+(\w+)',entry)[1]}
    return pins

def lef_pins(path,cell):
    text=Path(path).read_text()
    block=re.search(r'MACRO\s+'+re.escape(cell)+r'\b(.*?)END\s+'+re.escape(cell)+r'\b',text,re.S)
    if not block:raise ValueError(f'LEF macro not found: {cell}')
    pins={}
    for match in re.finditer(r'\bPIN\s+(\w+)\s+(.*?)END\s+\1\b',block[1],re.S):
        rects=[]
        layer=None
        for item in re.finditer(r'LAYER\s+(\w+)\s*;|RECT\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*;',match[2]):
            if item[1]:layer=item[1]
            else:rects.append((layer,tuple(float(v) for v in item.groups()[1:])))
        pins[match[1]]=rects
    return pins

def assemble(path,ring_path,manifest,workspace):
    import gdstk
    path,workspace=Path(path),Path(workspace)
    pdk=Path(manifest['pdk_root'])/'gf180mcuD'
    sc=pdk/'libs.ref/gf180mcu_fd_sc_mcu7t5v0'
    layers=stream_map(pdk/'libs.tech/klayout/tech/gf180mcu.map')
    for name in ['Metal2','Metal3','Metal4','Metal5','Via2','Via3','Via4']:
        if name not in layers:raise ValueError(f'Missing stream mapping {name}')
    tech=(sc/'techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef').read_text()
    minimum_widths={}
    for name in ('Metal2','Metal3','Metal4','Metal5'):
        block=re.search(r'^LAYER\s+'+name+r'\s*$(.*?)^END\s+'+name+r'\s*$',tech,re.S|re.M)
        minimum_widths[name]=float(re.search(r'\bMINWIDTH\s+([\d.]+)',block[1])[1])
    vias={}
    for i in range(2,5):
        m=re.search(r'\bVIA\s+(Via'+str(i)+r'_HH)\s+DEFAULT(.*?)END\s+\1',tech,re.S)
        if not m:raise ValueError(f'Missing default Via{i}_HH')
        via=[]
        layer=None
        for t in re.finditer(r'LAYER\s+(\w+)\s*;|RECT\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*;',m[2]):
            if t[1]:layer=t[1]
            else:via.append((layer,tuple(float(v) for v in t.groups()[1:])))
        vias[i]=via
    ringlib=gdstk.read_gds(str(ring_path))
    ring=next(c for c in ringlib.cells if c.name=='RING_PAD')
    lib=gdstk.Library(unit=ringlib.unit,precision=ringlib.precision)
    lib.add(*ringlib.cells)
    top=lib.new_cell(manifest['top'])
    top.add(gdstk.Reference(ring))
    cores={}
    obstacles=[]
    for block in manifest['cores']:
        origin=tuple(block['origin_um'])
        source=gdstk.read_gds(str(workspace/block['gds']))
        if source.unit!=lib.unit:raise ValueError('Core GDS units differ from ring units')
        core=next((c for c in source.cells if c.name==block['top']),None)
        if core is None:raise ValueError(f'Core top not found: {block["top"]}')
        for cell in source.cells:cell.name=block['instance']+'__'+cell.name
        lib.add(*source.cells)
        reference=gdstk.Reference(core,origin)
        top.add(reference)
        bbox=reference.bounding_box()
        (x0,y0),(x1,y1)=bbox
        if x0<390 or y0<390 or x1>2580 or y1>2580:raise ValueError('Core violates usable ring opening')
        for other in obstacles:
            if x0<other[2] and x1>other[0] and y0<other[3] and y1>other[1]:raise ValueError('Overlapping core blocks')
        obstacles.append((x0-8,y0-8,x1+8,y1+8))
        pins=def_pins(workspace/block['def'])
        cores[block['instance']]={'cell':core,'origin':origin,'bbox':bbox,'pins':pins,'def':block['def']}
    shapes={}
    records=[]
    def line(net,points,layer,width=0.4):
        width=max(width,minimum_widths[layer])
        points=[tuple(round(float(v),3) for v in p) for p in points]
        points=[p for i,p in enumerate(points) if i==0 or p!=points[i-1]]
        if len(points)<2:return
        polys=gdstk.FlexPath(points,width,layer=layers[layer],datatype=0).to_polygons()
        top.add(*polys)
        shapes.setdefault(net,[]).extend(polys)
    def via(net,point,start,end):
        lo,hi=sorted((int(start[-1]),int(end[-1])))
        for i in range(lo,hi):
            if i not in vias:raise ValueError(f'No via stack for layer {i}')
            for layer,(x0,y0,x1,y1) in vias[i]:
                poly=gdstk.rectangle((point[0]+x0,point[1]+y0),(point[0]+x1,point[1]+y1),layer=layers[layer])
                top.add(poly);shapes.setdefault(net,[]).append(poly)
    def transform(ref,point):
        x,y=point
        if ref.x_reflection:y=-y
        angle=ref.rotation or 0
        return (ref.origin[0]+x*math.cos(angle)-y*math.sin(angle),ref.origin[1]+x*math.sin(angle)+y*math.cos(angle))
    pin_cache={}
    def padpin(ref,name):
        cell=ref.cell
        if cell.name not in pin_cache:pin_cache[cell.name]=lef_pins(pdk/f'libs.ref/gf180mcu_fd_io/lef/{cell.name}.lef',cell.name)
        options=[r for layer,r in pin_cache[cell.name][name] if layer=='Metal2']
        if not options:raise ValueError(f'No Metal2 pin {cell.name}/{name}')
        rect=max(options,key=lambda r:r[3])
        local=((rect[0]+rect[2])/2,min(rect[3]-0.5,349.5))
        if not gdstk.inside([local],cell.get_polygons(layer=layers['Metal2'],datatype=0))[0]:raise ValueError(f'Pad endpoint is not actual metal: {name}')
        return transform(ref,local),local
    occupied=set()
    reserved={}
    grid=10.0
    # Reserve the actual straight Metal4 PDN escapes before signal routing.
    # This prevents a later supply drop from cutting a signal on the same layer.
    for instance,block in cores.items():
        text=(workspace/block['def']).read_text()
        dbu=int(re.search(r'UNITS DISTANCE MICRONS\s+(\d+)',text)[1])
        special=re.search(r'SPECIALNETS\s+\d+\s*;(.*?)END SPECIALNETS',text,re.S)[1]
        for k,net in enumerate(('VDD','VSS')):
            entry=re.search(r'\n\s*-\s+'+net+r'\b(.*?);',special,re.S)
            stripe=re.search(r'(?:ROUTED|NEW)\s+Metal4\s+[1-9]\d*\s+\+ SHAPE STRIPE\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)',entry[1])
            x=int(stripe[1])/dbu+block['origin'][0]
            bottom=block['bbox'][0][1]
            for gx in set((math.floor(x/grid),math.ceil(x/grid))):
                for gy in range(math.floor((bottom-180)/grid),math.ceil((bottom+25)/grid)+1):reserved[(gx,gy,0)]=net
    def point(n):return (n[0]*grid,n[1]*grid)
    def free(n,net):
        x,y=point(n)
        return 385<=x<=2590 and 385<=y<=2590 and not any(a<=x<=c and b<=y<=d for a,b,c,d in obstacles) and n not in occupied and reserved.get(n,net)==net
    def node(p,net):
        x,y=round(p[0]/grid),round(p[1]/grid)
        candidates=[(x+dx,y+dy,0) for dx in range(-3,4) for dy in range(-3,4)]
        candidates.sort(key=lambda n:(point(n)[0]-p[0])**2+(point(n)[1]-p[1])**2)
        return next(n for n in candidates if free(n,net))
    def gridroute(net,a,b):
        start,end=node(a,net),node(b,net)
        if start in occupied or end in occupied:raise ValueError(f'Occupied endpoint: {net}')
        queue=[(0,0,start)];previous={start:None};cost={start:0}
        while queue:
            _,distance,current=heapq.heappop(queue)
            if current==end:break
            if distance!=cost[current]:continue
            x,y,z=current
            candidates=[(x-1,y,z),(x+1,y,z)] if z==0 else [(x,y-1,z),(x,y+1,z)]
            candidates.append((x,y,1-z))
            for nxt in candidates:
                if nxt not in (start,end) and not free(nxt,net):continue
                step=4 if nxt[2]!=z else 1
                nc=distance+step
                if nc<cost.get(nxt,float('inf')):
                    cost[nxt]=nc;previous[nxt]=current
                    h=abs(nxt[0]-end[0])+abs(nxt[1]-end[1])
                    heapq.heappush(queue,(nc+h,nc,nxt))
        if end not in previous:raise ValueError(f'Cannot route {net}')
        route=[];c=end
        while c is not None:route.append(c);c=previous[c]
        route.reverse();occupied.update(route)
        line(net,[a,(a[0],point(start)[1]),point(start)],'Metal4')
        line(net,[b,(b[0],point(end)[1]),point(end)],'Metal4')
        for u,v in zip(route,route[1:]):
            if u[2]!=v[2]:via(net,point(u),'Metal4','Metal5')
            else:line(net,[point(u),point(v)],'Metal4' if u[2]==0 else 'Metal5')
        return route
    assigned={}
    for i,connection in enumerate(manifest['connections']):
        net=connection['net'];refidx=connection['pad_reference']
        if refidx in assigned:raise ValueError(f'Pad reused: {refidx}')
        ref=ring.references[refidx]
        direction=connection['direction']
        pname='Y' if direction=='INPUT' else 'A'
        padpoint,local=padpin(ref,pname)
        pad_escape=transform(ref,(local[0],390+10*i))
        line(net,[padpoint,pad_escape],'Metal2')
        via(net,pad_escape,'Metal2','Metal4')
        block=cores[connection['core']]
        pin=block['pins'].get(connection['pin'])
        if not pin:raise ValueError(f'Missing core pin {connection["pin"]}')
        if pin['direction']!=direction:raise ValueError('Pad/core direction mismatch')
        ox,oy=block['origin'];cx,cy=pin['point']
        corepoint=(cx+ox,cy+oy)
        if not gdstk.inside([(cx,cy)],block['cell'].get_polygons(layer=layers[pin['layer']],datatype=0))[0]:raise ValueError(f'Core pin is not actual GDS metal: {net}')
        (x0,y0),(x1,y1)=block['bbox']
        side=min([(abs(corepoint[0]-x0),'W'),(abs(corepoint[0]-x1),'E'),(abs(corepoint[1]-y0),'S'),(abs(corepoint[1]-y1),'N')])[1]
        margin=30+10*i
        end={'W':(x0-margin,corepoint[1]),'E':(x1+margin,corepoint[1]),'S':(corepoint[0],y0-margin),'N':(corepoint[0],y1+margin)}[side]
        line(net,[corepoint,end],pin['layer'])
        if x1-x0<100 and side in ('S','N') and pin['layer']=='Metal2':
            # A tiny macro can have several pins near the same PDN column.
            # Fan out on Metal3 before reaching Metal4, preserving isolation
            # from both the Metal2 pin escapes and the Metal4 power drops.
            fanout=(x0-30 if corepoint[0]<(x0+x1)/2 else x1+30,end[1])
            via(net,end,'Metal2','Metal3')
            line(net,[end,fanout],'Metal3')
            via(net,fanout,'Metal3','Metal4')
            end=fanout
        else:
            via(net,end,pin['layer'],'Metal4')
        route=gridroute(net,pad_escape,end)
        assigned[refidx]=connection
        records.append({**connection,'pad_cell':ref.cell.name,'pad_pin':pname,'pad_point_um':padpoint,'core_point_um':corepoint,'core_layer':pin['layer'],'grid_steps':len(route),'pin_geometry_checked':True})
        top.add(gdstk.Label(f'PORT::{net}::pad',padpoint,layer=layers['Metal2'],texttype=10))
        top.add(gdstk.Label(f'PORT::{net}::core',corepoint,layer=layers[pin['layer']],texttype=10))
    # Local pad control ties. Metal2 escapes and Metal3 buses connect to the
    # actual VDD/VSS perimeter rails, with PDK Via2 landing geometry.
    ties=0
    for index,ref in enumerate(ring.references):
        cell=ref.cell.name
        if cell not in ('gf180mcu_fd_io__in_c','gf180mcu_fd_io__bi_t'):continue
        control={'PU':0,'PD':0}
        if cell.endswith('__bi_t'):
            active=assigned.get(index)
            output=bool(active and active['direction']=='OUTPUT')
            inputs=bool(active and active['direction']=='INPUT')
            control.update(CS=0,SL=0,IE=int(inputs),OE=int(output),PDRV0=0,PDRV1=0)
            if not output:control['A']=0
        for pin,value in control.items():
            _,local=padpin(ref,pin)
            net='VDD' if value else 'VSS';bus=366 if value else 358
            rail_y=314.5 if value else 321.5;rail_x=-12.5 if value else -8.5
            p0=transform(ref,local);p1=transform(ref,(local[0],bus))
            p2=transform(ref,(rail_x,bus));p3=transform(ref,(rail_x,rail_y));p4=transform(ref,(0.5,rail_y))
            line(net,[p0,p1],'Metal2');via(net,p1,'Metal2','Metal3')
            line(net,[p1,p2],'Metal3');via(net,p2,'Metal2','Metal3')
            line(net,[p2,p3],'Metal2');via(net,p3,'Metal2','Metal3');line(net,[p3,p4],'Metal3')
            ties+=1
    # Reject same-layer shorts among independently assigned signal nets and
    # the newly drawn control ties. Full-layout extraction is a separate check.
    power_records=[]
    for j,(instance,block) in enumerate(cores.items()):
        text=(workspace/block['def']).read_text()
        dbu=int(re.search(r'UNITS DISTANCE MICRONS\s+(\d+)',text)[1])
        special=re.search(r'SPECIALNETS\s+\d+\s*;(.*?)END SPECIALNETS',text,re.S)[1]
        ref=ring.references[335 if j==0 else 336]
        for k,net in enumerate(('VDD','VSS')):
            entry=re.search(r'\n\s*-\s+'+net+r'\b(.*?);',special,re.S)
            stripe=re.search(r'(?:ROUTED|NEW)\s+Metal4\s+[1-9]\d*\s+\+ SHAPE STRIPE\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)',entry[1])
            if not stripe:raise ValueError(f'Missing real core PDN stripe: {instance}/{net}')
            x,y,x2,y2=[int(v)/dbu for v in stripe.groups()]
            if x!=x2:raise ValueError('Expected vertical Metal4 power stripe')
            y=min(y,y2)
            if not gdstk.inside([(x,y+0.3)],block['cell'].get_polygons(layer=layers['Metal4'],datatype=0))[0]:raise ValueError('Core power endpoint misses actual GDS')
            ox,oy=block['origin']
            corepoint=(x+ox,y+oy+0.3)
            end=(corepoint[0],block['bbox'][0][1]-150-20*k)
            line(net,[corepoint,end],'Metal4',width=1.0)
            rail_y=314.5 if net=='VDD' else 321.5
            rail_x=-12.5 if net=='VDD' else -8.5
            local=(0.5,rail_y)
            if not gdstk.inside([local],ref.cell.get_polygons(layer=layers['Metal3'],datatype=0))[0]:raise ValueError('IO power rail endpoint misses actual GDS')
            p0=transform(ref,local);p1=transform(ref,(rail_x,rail_y));p2=transform(ref,(rail_x,390+20*k))
            line(net,[p0,p1],'Metal3',width=1.0);via(net,p1,'Metal2','Metal3')
            line(net,[p1,p2],'Metal2',width=0.4);via(net,p2,'Metal2','Metal4')
            gridroute(net,p2,end)
            power_records.append({'core':instance,'net':net,'pad_reference':335 if j==0 else 336,'pad_rail_point_um':p0,'core_point_um':corepoint,'pin_geometry_checked':True})
            top.add(gdstk.Label(f'PGPORT::{instance}/{net}::pad',p0,layer=layers['Metal3'],texttype=10))
            top.add(gdstk.Label(f'PGPORT::{instance}/{net}::core',corepoint,layer=layers['Metal4'],texttype=10))
    nets=list(shapes)
    for i,a in enumerate(nets):
        for b in nets[i+1:]:
            for layer in [layers[k] for k in ('Metal2','Metal3','Metal4','Metal5')]:
                pa=[p for p in shapes[a] if p.layer==layer]
                pb=[p for p in shapes[b] if p.layer==layer]
                if pa and pb and gdstk.boolean(pa,pb,'and',precision=0.001):raise ValueError(f'New-route short: {a}/{b} on stream layer {layer}')
    path.parent.mkdir(parents=True,exist_ok=True)
    lib.write_gds(str(path))
    reread=gdstk.read_gds(str(path))
    resulttop=next(c for c in reread.cells if c.name==manifest['top'])
    if len(resulttop.references)!=len(cores)+1:raise ValueError('GDS hierarchy readback mismatch')
    census=dict(Counter(r.cell.name for r in ring.references))
    pad_summary={'analog':census.get('gf180mcu_fd_io__asig_5p0',0),
                 'digital_inputs':census.get('gf180mcu_fd_io__in_c',0),
                 'bidirectional':census.get('gf180mcu_fd_io__bi_t',0),
                 'dvdd':census.get('gf180mcu_fd_io__dvdd',0),'dvss':census.get('gf180mcu_fd_io__dvss',0)}
    pad_summary['total_io']=sum(pad_summary.values())
    pad_summary['corners']=census.get('gf180mcu_fd_io__cor',0)
    pad_summary['total_cells']=pad_summary['total_io']+pad_summary['corners']
    report={'top_cell':manifest['top'],'core_count':len(cores),'cores':list(cores),'ring_cell':ring.name,
            'merged_cells':len(lib.cells),'routes_signal':len(records),'routes_total':len(records)+len(power_records),
            'routes_power':len(power_records),'pad_control_ties':ties,'stream_layers':layers,
            'actual_pad_census':census,'actual_pad_summary':pad_summary,'minimum_route_widths_um':minimum_widths,
            'pin_geometry_checked':True,'new_route_shorts':0,'full_chip_drc_passed':False,'full_chip_lvs_passed':False,
            'power_routes_to_both_cores':True,'connections':records,'power_connections':power_records,'gds_bytes':path.stat().st_size,
            'route_layers':','.join(f'{layers[x]}/0' for x in ('Metal2','Metal3','Metal4','Metal5'))}
    (path.parent/'pin_assembly_report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
