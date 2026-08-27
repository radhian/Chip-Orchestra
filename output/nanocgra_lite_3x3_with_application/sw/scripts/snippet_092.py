import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
vs = d['vectors']
# rx_byte at 4340 is 165 = 0xA5 = 10100101
# Data bits sampled at ticks 1..8 (positions 867, 1301, 1735, 2169, 2603, 3037, 3471, 3905)
# rx_in at those: 1,0,1,0,0,1,0,1 -> LSB first -> bit0=1, bit1=0, bit2=1, bit3=0, bit4=0, bit5=1, bit6=0, bit7=1
# = 10100101 = 0xA5 = 165. Correct!
# Now check: rx_byte appears at position 4340, but rx_valid=1 at 3905.
# 4340 = 3905 + 435 = 3905 + 434 + 1. Hmm.
# Actually 4340 = 10*434 = 4340. And 3905 = 9*434 + (-1) = 9*434 - 1? No: 9*434=3906, so 3905=9*434-1.
# Wait: 433 + 8*434 = 433+3472 = 3905. So tick 8 at 3905.
# rx_valid at 3905 (tick 8, when bit_idx reaches 8).
# rx_byte at 4340 = tick 9 (stop bit). So rx_byte is registered at the NEXT tick after valid?
# Let me check: in the golden model, at tick 8 (bit_idx==8), rx_byte=shreg and rx_valid=1.
# But the vector shows rx_byte at 4340 not 3905. 
# Actually the test might check rx_byte only when rx_valid=1, and the vector at 3905 has rx_valid=1 but no rx_byte.
# The vector at 4340 has rx_byte=165. So the test checks rx_byte at the cycle AFTER rx_valid?
# Or maybe rx_byte is only checked at certain vectors.
# Let me look at what's at 3905 and 4340
print('at 3905:', vs[3905]['expected'])
print('at 4340:', vs[4340]['expected'])
print('at 4339:', vs[4339]['expected'])
# So rx_valid=1 at 3905, rx_byte=165 at 4340.
# In the golden model: at tick 8, rx_byte=shreg, rx_valid=1. Both happen at the same step.
# But the RTL: rx_byte is registered, so at posedge of cycle 3905, rx_byte gets the value.
# The test vector at index 3905 represents the state AFTER clock edge 3905.
# Hmm, this is confusing. Let me check the test file.