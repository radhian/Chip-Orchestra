import json
with open('golden/vectors/uart_rx.json') as f:
    d = json.load(f)
# Ticks at: 433, 867, 1301, 1735, 2169, 2603, 3037, 3471, 3905
# rx_in at ticks: 0, 1, 0, 1, 0, 0, 1, 0, 1
# prev_line tracking (updated at each tick):
# tick 0 (433): rx_in=0, prev_line was 1 (initial) -> FALLING EDGE! Start detected. DATA, bit_idx=0. prev_line=0
# tick 1 (867): rx_in=1, DATA, shreg[0]=1, bit_idx=1. prev_line=1
# tick 2 (1301): rx_in=0, DATA, shreg[1]=0, bit_idx=2. prev_line=0
# tick 3 (1735): rx_in=1, DATA, shreg[2]=1, bit_idx=3. prev_line=1
# tick 4 (2169): rx_in=0, DATA, shreg[3]=0, bit_idx=4. prev_line=0
# tick 5 (2603): rx_in=0, DATA, shreg[4]=0, bit_idx=5. prev_line=0
# tick 6 (3037): rx_in=1, DATA, shreg[5]=1, bit_idx=6. prev_line=1
# tick 7 (3471): rx_in=0, DATA, shreg[6]=0, bit_idx=7. prev_line=0
# tick 8 (3905): rx_in=1, DATA, shreg[7]=1, bit_idx=8 -> rx_byte=shreg, rx_valid=1! prev_line=1
# shreg = bit7..bit0 = 10100101 = 0xA5 = 165. YES! rx_byte=165 at index 4340.
# Wait, rx_byte=165 at 4340, but rx_valid=1 at 3905. 
# The golden model sets rx_byte=shreg AND rx_valid=1 at the same step. So at cycle 3905, both should be set.
# But the vector at 3905 only shows rx_valid=1 (no rx_byte), and at 4340 shows rx_byte=165.
# This is because the test only checks rx_byte when rx_valid=1, and the vector format may only record rx_byte at certain points.
# Actually, looking at the vector: at 3905, exp={'rx_valid': 1} (no rx_byte key).
# At 4340, exp={'rx_byte': 165} (no rx_valid key). 
# This means the test only checks specific outputs at specific cycles.
# So the golden model works: start detected at tick 0 (cycle 433), 8 data bits at ticks 1-8, valid at tick 8 (cycle 3905).
# 
# NOW: the key question is whether the RTL uart_rx matches this timing.
# The RTL detects falling edge at a baud_tick where prev_line=1 and rx_in=0.
# Then samples 8 data bits at subsequent baud_ticks.
# This matches the golden model exactly!
# 
# But wait - the RTL has a subtle issue. In the RTL:
# if (bit_idx == 3'd7) begin
#     rx_byte <= {rx_in, shreg[7:1]};  // bit7 is rx_in, bits 6..1 from shreg
#     state <= STOP;
#     rx_valid <= 1'b1;
# end
# This assigns rx_byte = {rx_in, shreg[7:1]}. But shreg[bit_idx] <= rx_in was also executed!
# In Verilog, non-blocking assignments: shreg[bit_idx] <= rx_in happens, AND rx_byte <= {rx_in, shreg[7:1]}.
# But shreg[7:1] uses the OLD value of shreg (before the non-blocking update).
# So rx_byte = {rx_in, old_shreg[7:1]} = {bit7, bit6, bit5, bit4, bit3, bit2, bit1}
# But we want rx_byte = {bit7, bit6, bit5, bit4, bit3, bit2, bit1, bit0}
# where bit0 was sampled at the first DATA tick and stored in shreg[0].
# So rx_byte should be the full shreg after bit7 is added: {rx_in, shreg[6:0]}? No...
# shreg[0]=bit0, shreg[1]=bit1, ..., shreg[7]=bit7(=rx_in at this tick)
# rx_byte should be shreg = {shreg[7], shreg[6], ..., shreg[0]} = {rx_in, shreg[6:0]}
# But the RTL does: rx_byte <= {rx_in, shreg[7:1]}
# shreg[7:1] = {shreg[7], shreg[6], shreg[5], shreg[4], shreg[3], shreg[2], shreg[1]}
# But shreg[7] hasn't been written yet (old value = 0 or whatever).
# So rx_byte = {rx_in, old_shreg[7], old_shreg[6], ..., old_shreg[1]}
# = {bit7, 0, bit6, bit5, bit4, bit3, bit2, bit1} -- WRONG! Missing bit0, extra 0.
# 
# The correct assignment should be: rx_byte <= {rx_in, shreg[6:0]};
# This gives {bit7, bit6, bit5, bit4, bit3, bit2, bit1, bit0} = correct!
print("Analysis complete: uart_rx has a bug in rx_byte assignment")
print("Should be: rx_byte <= {rx_in, shreg[6:0]}")
print("Currently: rx_byte <= {rx_in, shreg[7:1]}")