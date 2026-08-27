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

# Simulate the RTL datapath exactly as the hardware does it.
# The controller: on rx_valid, sets pixel_shift=1, pixel_in=rx_byte, 
#   col_cnt <= (pixel_cnt+1)%32, row_cnt <= (pixel_cnt+1)/32, pixel_cnt <= pixel_cnt+1
# The line buffers shift on pixel_shift with pixel_in.
# The window_3x3: win is combinational = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
#   where sr registers update on posedge with shift_en.
# The sobel_out is combinational from win.
# The controller captures sobel_out into result_reg at the SAME posedge as rx_valid.
# So the captured sobel_out uses the PRE-edge values of sr, lb_data, col_cnt, pixel_in.

# Let me simulate this precisely.
def rtl_simulate(pixels):
    # Line buffers (both identical since same pixel_in)
    lb = [0]*32  # both lb0 and lb1 are the same
    # Window shift registers (pre-edge values)
    sr0 = [0,0,0]  # row N-2
    sr1 = [0,0,0]  # row N-1
    sr2 = [0,0,0]  # row N
    results = []
    pixel_cnt = 0
    col_cnt = 0  # registered, starts at 0
    row_cnt = 0
    
    for k, px_in in enumerate(pixels):
        px_in = int(px_in) & 0xFF
        # PRE-edge: combinational values used for sobel computation
        # col_cnt is the registered value from PREVIOUS cycle
        # At the start: col_cnt=0 (from reset). 
        # After first rx_valid: col_cnt becomes 1 (next cycle).
        # So when processing pixel k, col_cnt = k (if k>0) or 0 (if k=0)?
        # Actually: pixel_cnt starts at 0. On first rx_valid (pixel 0):
        #   col_cnt <= (0+1)%32 = 1. So NEXT cycle col_cnt=1.
        #   But the sobel capture uses the CURRENT col_cnt=0.
        # On second rx_valid (pixel 1): col_cnt is now 1 (from previous update).
        #   col_cnt <= (1+1)%32 = 2. sobel uses col_cnt=1.
        # So when processing pixel k (0-indexed), the col_cnt used for sobel = k.
        # (for k=0: col_cnt=0, k=1: col_cnt=1, etc.)
        # Wait, that's only true if rx_valid happens every cycle. But rx_valid is once per UART byte.
        # Between rx_valids, col_cnt doesn't change. So yes, when pixel k arrives, col_cnt = k%32.
        
        cur_col = pixel_cnt % 32  # current registered col_cnt
        cur_row = pixel_cnt // 32  # current registered row_cnt
        
        # Line buffer tap (pre-edge): mem[cur_col]
        # But wait, the line buffer has been shifting. After k pixels shifted in,
        # mem[i] = pixel[k-1-(31-i)] = pixel[k-32+i] for k>=32, or pixel[k-1-(31-i)] for k<32
        # Actually after shifting in k pixels (pixels 0..k-1):
        # mem[31] = pixel[k-1], mem[30] = pixel[k-2], ..., mem[31-j] = pixel[k-1-j]
        # mem[i] = pixel[k-1-(31-i)] = pixel[k-32+i]
        # For k<32: mem[31-k+1..31] = pixel[0..k-1], mem[0..31-k] = 0
        
        # The tap is at cur_col = k%32. 
        # mem[cur_col] = pixel[k-32+cur_col] = pixel[k-32+(k%32)]
        # If k<32: mem[cur_col] = pixel[k-1-(31-cur_col)] = pixel[k-32+cur_col]
        #   For k=cur_col (first row): mem[cur_col] = pixel[cur_col-32+cur_col] = pixel[2*cur_col-32]
        #   That's negative for cur_col<16, so 0.
        # This is clearly wrong - the shift register doesn't map to columns.
        
        # Let me just compute it directly.
        # After k pixels shifted (k = pixel_cnt before this cycle):
        lb_val = lb[cur_col] if cur_col < 32 else 0
        
        # Both line buffers are identical
        lb_n2 = lb_val  # row_cnt[0] ? lb1 : lb0, but both same
        lb_n1 = lb_val
        
        # Window (combinational, pre-edge):
        # win = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
        win = [sr0[1], sr0[2], lb_n2,
               sr1[1], sr1[2], lb_n1,
               sr2[1], sr2[2], px_in]
        
        # Check if window valid: col_cnt >= 2 and row_cnt >= 2
        # But the controller checks (pixel_cnt+1) for the NEW value
        new_row = (pixel_cnt + 1) // 32
        new_col = (pixel_cnt + 1) % 32
        if new_row >= 2 and new_col >= 2:
            gx, gy, out = sobel_compute(win)
            results.append(out)
        
        # Now apply the clock edge: update line buffer and shift registers
        # Line buffer: shift left, push px_in at right
        lb = lb[1:] + [px_in]
        # Shift registers: shift left, push new column
        sr0 = sr0[1:] + [lb_n2]  # but lb_n2 is the PRE-edge value
        sr1 = sr1[1:] + [lb_n1]
        sr2 = sr2[1:] + [px_in]
        
        pixel_cnt += 1
    
    return results

results = rtl_simulate(flat)
print("RTL sim results len:", len(results), "expected 900")
print("First 20 RTL sim:", results[:20])
print("First 20 chip:   ", cmem[:20])
print("First 20 golden: ", [68,56,58,60,62,60,62,60,60,58,60,60,60,58,58,60,60,58,62,62])
print("Match chip?", results[:20] == cmem[:20])