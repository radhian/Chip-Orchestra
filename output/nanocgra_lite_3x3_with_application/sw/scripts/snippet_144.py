import json
# The vector file transitions are at vecs 430, 1732, 3468, 4336.
# The golden model with tx_start@0 gives transitions at 433, 867, 1301, 1735, ...
# The vector file has FEWER transitions (430, 1732, 3468, 4336) — only 4 transitions
# in the first frame, while the golden model has 9 (one per bit).
# 
# Vector: 430(0), 1732(1), 3468(0), 4336(1,done)
# Differences: 1732-430=1302, 3468-1732=1736, 4336-3468=868
# These are roughly 3*434=1302, 4*434=1736, 2*434=868
# 
# This looks like the vector file was generated with a DIFFERENT data pattern
# where consecutive identical bits are merged. Let me figure out the data byte.
# 
# Frame: start(0) at 430, then data bits...
# bit0 at 430+434=864, bit1 at 1298, bit2 at 1732, bit3 at 2166, ...
# But the vector shows tx_out=1 at 1732. So bit2=1.
# tx_out=0 at 3468. 3468-430=3038. 3038/434=7. So that's bit7 at 430+7*434=3468.
# bit7=0. Then stop at 430+8*434=3902? But vector shows stop at 4336.
# 4336-430=3906=9*434. So the stop bit is at position 9, meaning 9 bits after start?
# That's start + 8 data + stop = 10 bits, but the stop is at 9*434 after start.
# 
# Actually: start bit occupies 430..863 (434 cycles), bit0 at 864..1297, etc.
# bit7 at 430+8*434=3902..4335, stop at 4336. 
# tx_out=0 at 430 (start), 1 at 1732 (bit2), 0 at 3468 (bit7), 1 at 4336 (stop, done).
# 
# So the data byte has: bit0=?, bit1=?, bit2=1, bit3=?, bit4=?, bit5=?, bit6=?, bit7=0
# The transitions only show where tx_out CHANGES. So:
# 430: 0 (start)
# 1732: 1 (bit2=1, bits 0,1 were also 0 so no transition)
# 3468: 0 (bit7=0, bits 3-6 were 1 so no transition until bit7)
# 4336: 1 (stop)
# 
# So bits 0,1 = 0,0; bit2=1; bits 3,4,5,6=1,1,1,1; bit7=0
# Data = 0b00111100 = 0x3C = 60... wait, LSB first: bit0=0,bit1=0,bit2=1,bit3=1,bit4=1,bit5=1,bit6=1,bit7=0
# = 0b01111100 = 0x7C? No. LSB first: bit0 is LSB.
# byte = bit0 + bit1*2 + bit2*4 + bit3*8 + bit4*16 + bit5*32 + bit6*64 + bit7*128
# = 0 + 0 + 4 + 8 + 16 + 32 + 64 + 0 = 124 = 0x7C
# 
# Hmm, but the vector file has tx_start=0 for all vectors. So how was this generated?
# The tx_start must have been pulsed BEFORE the recorded vectors started, or the vector
# generation has a bug where tx_start isn't recorded.
#
# Let me check: if tx_start was pulsed at vec -3 (3 cycles before vec 0), then
# the first baud tick at vec 433 would see start_req and begin. But the vector shows
# the start bit at vec 430, which is 3 cycles before the first baud tick.
# 
# Actually wait — maybe the vector generation used a 3-cycle earlier tx_start.
# If tx_start=1 at vec 0, first tick at 433, start bit at 433. Vector shows 430.
# Difference = 3. So maybe the baud_gen in the vector generation had div=431?
# 
# Or maybe the vectors were generated with the RTL simulation, not the golden model.
# The RTL baud_gen.v — let me check its divider value.

print("Checking RTL baud_gen divider...")