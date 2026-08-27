import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']
flat = [p for row in px for p in row]

# My simulation doesn't exactly match the chip, but it's close in pattern.
# The chip has alternating high/low values which suggests the row_cnt[0] swap IS doing something.
# Wait - both line buffers are identical, so lb_n2 and lb_n1 are the same. But the window
# shift registers sr0 and sr1 ARE different because they accumulate different lb values over time...
# No, they get the same lb_n2=lb_n1 each cycle, so sr0 and sr1 are identical too!
# Unless... the row_cnt[0] swap means lb_n2 and lb_n1 swap between lb0 and lb1.
# But lb0 and lb1 are identical (same pixel_in, same shift_en). So the swap is meaningless.

# Let me look more carefully at the chip output. The alternating pattern:
# chip: 100, 132, 10, 132, 12, 134, 12, 134, 12, 136, 16, 136, 20
# indices: 0    1    2   3    4    5    6   7    8   9   10   11  12
# Even indices: 100, 10, 12, 12, 12, 16, 20
# Odd indices: 132, 132, 134, 134, 136, 136
# The odd indices have bit 7 set (0x80). 132=0x84, 134=0x86, 136=0x88.
# Even: 100=0x64, 10=0x0a, 12=0x0c, 12=0x0c, 12=0x0c, 16=0x10, 20=0x14

# The odd values look like they have 0x80 OR'd in. 132=0x84, 0x84-0x80=0x04. 
# 134=0x86, -0x80=0x06. 136=0x88, -0x80=0x08.
# Even: 10=0x0a, 12=0x0c, 12=0x0c, 12=0x0c, 16=0x10, 20=0x14
# Golden: 68=0x44, 56=0x38, 58=0x3a, 60=0x3c, 62=0x3e, 60=0x3c, 62=0x3e, 60=0x3c

# Hmm, the golden values are all in 0x38-0x44 range. The chip values are scattered.
# This really looks like the window pixels are completely wrong.

# Let me try a different simulation approach - maybe the timing of when sobel_out is captured
# is different. The controller captures sobel_out when rx_valid AND new_row>=2 AND new_col>=2.
# But sobel_out is combinational from the CURRENT win, which uses CURRENT (pre-edge) sr/lb/col_cnt.
# The question is: what are the sr/lb values at the moment of capture?

# Actually, I realize the issue might be more subtle. The controller is in S_RECV.
# When it gets rx_valid, it checks if (pixel_cnt+1) has row>=2 and col>=2.
# If yes, it captures sobel_out and goes to S_TX_RESULT.
# But then it goes to S_NEXT (waits for tx_done), then back to S_RECV.
# During S_TX_RESULT and S_NEXT, no pixels are being accepted (pixel_shift=0).
# So pixels are being DROPPED while transmitting results!

# Let me check: the TB sends a pixel, then tries to receive. The receive takes ~10 baud periods.
# During that time, the controller is in S_TX_RESULT/S_NEXT and NOT accepting pixels.
# But the TB sends the next pixel only after recv_byte returns (with or without timeout).
# So the TB is sending pixels one at a time, waiting for a response each time.
# The controller accepts a pixel, if valid window captures result and goes to TX.
# While in TX, it ignores rx_valid. The TB's next send_byte happens after recv_byte.

# Actually, the TB calls recv_byte after EVERY send_byte. recv_byte waits for a start bit
# with timeout of 3*BAUD_DIV. If the chip is transmitting, it catches it. If not, timeout.
# So the flow is: send pixel -> try to receive (timeout if no result) -> send next pixel.
# The controller: accepts pixel in S_RECV. If valid window, captures and goes to S_TX_RESULT.
# Next cycle: S_TX_RESULT (tx_start=1). Then S_NEXT (wait for tx_done).
# tx_done comes after ~10 baud periods. Then back to S_RECV.
# Meanwhile the TB has finished send_byte and is in recv_byte, waiting for the TX.
# So the timing should work out - the chip transmits, the TB receives.

# But the KEY issue remains: the line buffers are both identical.
# Let me check if maybe the design intended lb1 to get lb0's output instead of pixel_in.
# In the golden model top.py: 
#   self.lb1.step(clk, rst_n, 1, self.lb0.row[-1])  -- lb1 gets lb0's oldest pixel
#   self.lb0.step(clk, rst_n, 1, self.ctrl.pixel_in)  -- lb0 gets the new pixel
# So lb0 stores the most recent row, lb1 stores the row before that.
# But in the RTL, BOTH get pixel_in! That's the bug.

print("BUG CONFIRMED: In the RTL top module, both line buffers (u_lb0 and u_lb1)")
print("receive the same pixel_in. The golden model has lb1 receive lb0's oldest pixel")
print("(lb0.row[-1]) while lb0 receives the new pixel. This means the two line buffers")
print("in the RTL are always identical, so the window never gets proper N-2 and N-1 rows.")