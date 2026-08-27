import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
vs = d['vectors']
# Show full expected at first valid
p = 3905
print('expected at p:', vs[p]['expected'])
# Show rx_in from p-20 to p+5
print('rx_in p-20..p+5:', [vs[j]['inputs']['rx_in'] for j in range(p-20, p+6)])
# The first valid is at index 3905. 3905 = 9*434 + 19? Let's check: 3905/434 = 9.0
print('3905/434 =', 3905/434)
print('3905 = 9*434 +', 3905 - 9*434)
# So 9 baud ticks. Start detection at tick 0, then 8 data bits at ticks 1-8, valid at tick 8.
# tick at 433, 867, ... 9th tick at 433+8*434 = 433+3472 = 3905. Yes!
# So rx_valid at 3905 = 9th baud tick. rx_byte should be assembled.
# But expected doesn't have rx_byte? Let me check all keys
print('all expected keys:', set(k for v in vs for k in v['expected']))