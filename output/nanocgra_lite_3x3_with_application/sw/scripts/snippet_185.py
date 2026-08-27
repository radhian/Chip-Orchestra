import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('waves/chip_output.mem') as f:
    lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('//')]
cmem = [int(line,16) for line in lines]
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']

# Let me simulate the RTL's broken line buffer scheme and see what windows it produces.
# RTL: two line buffers lb0, lb1, both shift on every pixel_shift with pixel_in.
# lb_n2 = row_cnt[0] ? lb1_col : lb0_col
# lb_n1 = row_cnt[0] ? lb0_col : lb1_col
# where lb_col = mem[col_cnt] after shift.

# Actually, the line buffers BOTH get the same pixel_in and both shift. So they're identical!
# That means lb0 and lb1 always have the same content. The row_cnt[0] swap is meaningless.
# This is a major bug - the two line buffers should store DIFFERENT rows.

# Let me simulate: both LBs identical, shifting every pixel.
# After k+1 pixels shifted, mem[i] = pixel[k - (31-i)] = pixel[k-31+i] (for k>=31)
# For k<31, mem[31-j] = pixel[k-j], mem[0..30-k-1] = 0 (initial)

# The tap is at col_cnt = (k+1)%32.
# Let me just simulate the whole RTL datapath in Python and see what output it produces.

def rtl_simulate(pixels):
    """Simulate the RTL's broken datapath."""
    # Two line buffers (identical, both shift with pixel_in)
    lb0 = [0]*32
    lb1 = [0]*32
    # Window shift registers
    sr0 = [0,0,0]  # row N-2
    sr1 = [0,0,0]  # row N-1
    sr2 = [0,0,0]  # row N
    results = []
    pixel_cnt = 0
    for k, px in enumerate(pixels):
        # Before the clock edge: col_cnt and row_cnt are set to (pixel_cnt+1) values
        # But actually in RTL, col_cnt/row_cnt are registered, updated AT the edge.
        # The window combinational logic uses the CURRENT sr values + lb_data + pixel_in.
        # The lb_data is tapped from line buffer BEFORE the shift (combinational read of current mem).
        # Wait - the shift happens at posedge. The combinational win uses lb0_data which is 
        # combinational from mem (current values, before shift). And col_cnt is the value
        # AFTER this edge (registered). So there's a mismatch: col_cnt is one ahead of the line buffer.
        
        # Actually let me re-read the controller. On rx_valid in S_RECV:
        #   col_cnt <= (pixel_cnt + 1) & 0x1F;  -- this is the NEW col_cnt (next cycle)
        #   pixel_shift <= 1;  -- shift happens this cycle
        # So at the posedge: line buffer shifts (gets new pixel), col_cnt updates to (pixel_cnt+1)%32
        # In the NEXT cycle: col_cnt = (pixel_cnt+1)%32, line buffer has been shifted.
        # The window combinational logic uses sr registers (updated at same posedge) + lb_data.
        # lb_data = mem[col_cnt] where mem is post-shift and col_cnt is post-update.
        
        # So the sobel_out that gets captured is from the cycle AFTER rx_valid.
        # But wait - in S_RECV, when rx_valid, it captures sobel_out IMMEDIATELY (same cycle):
        #   result_reg <= sobel_out;
        # sobel_out is combinational from win, which uses sr registers (pre-edge) + lb_data (pre-edge)
        # and col_cnt (pre-edge, = old value). So the window uses OLD col_cnt and OLD line buffer.
        
        # Let me be precise. At the posedge where rx_valid=1:
        # Combinational signals BEFORE the edge:
        #   col_cnt = current registered value = (pixel_cnt) % 32  [from previous update]
        #   Actually no. Let me trace from reset.
        #   Reset: pixel_cnt=0, col_cnt=0, row_cnt=0
        #   Cycle 1: rx_valid=1 (first pixel). Combinational: col_cnt=0, pixel_shift will be set.
        #     sobel_out uses win with col_cnt=0, sr=0, lb_data=mem[0]=0 (line buffer empty)
        #     At posedge: pixel_cnt->1, col_cnt->1, line buffer shifts in pixel[0], sr shifts
        #     But result_reg captures sobel_out (computed with old values). Since row<2, no capture.
        #   ...
        # This is getting very complex. Let me just simulate cycle by cycle.
        pass
    
    # Actually, let me take a different approach. Let me check if the two line buffers being 
    # identical is the core issue, and what the output would be if we fix that.
    
    # The REAL issue: both line buffers get the SAME pixel_in and shift together.
    # They should be staggered: lb0 stores row N-2, lb1 stores row N-1.
    # In a proper design: lb1 shifts in the current pixel, lb0 shifts in lb1's oldest pixel.
    # Or: use a ping-pong / column-addressed approach.
    
    print("Core bug identified: both line buffers receive identical pixel_in and shift together.")
    print("They should be staggered to hold different rows (N-2 and N-1).")

rtl_simulate(None)