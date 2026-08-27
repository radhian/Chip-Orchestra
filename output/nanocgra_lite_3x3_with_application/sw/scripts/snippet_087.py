import json
with open('golden/vectors/baud_gen.json') as f:
    d = json.load(f)
ticks = [v['expected']['baud_tick'] for v in d['vectors']]
print('total vectors:', len(ticks))
print('num ticks:', sum(ticks))
# find positions of ticks
pos = [i for i,t in enumerate(ticks) if t==1]
print('tick positions (first 10):', pos[:10])
print('tick at index 433?', ticks[433] if len(ticks)>433 else 'N/A')
print('tick at index 434?', ticks[434] if len(ticks)>434 else 'N/A')
# The divider is 434. cnt counts 0..433, tick when cnt==433.
# So first tick after reset should be at cycle 433 (0-indexed) if cnt starts at 0.
# Let's check: golden model: cnt starts 0, tick when cnt==div-1=433, so first tick at cycle 433.
print('ticks[430:436]:', ticks[430:436])