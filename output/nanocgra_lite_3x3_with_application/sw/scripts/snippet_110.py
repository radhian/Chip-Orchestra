import json
for mod in ['uart_rx','uart_tx','baud_gen','reset_sync','sram_32b','mmio_bus']:
    with open(f'golden/vectors/{mod}.json') as f:
        d = json.load(f)
    v = d['vectors']
    print(f'{mod}: {len(v)} vectors, ports in={[p[0] for p in d["ports"]["inputs"]]}, out={[p[0] for p in d["ports"]["outputs"]]}')
    # show first vector expected
    if v:
        print('  first expected:', v[0].get('expected', {}))
        print('  first inputs:', {k:val for k,val in v[0]['inputs'].items() if k!='clk'})