import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']
flat = [p for row in px for p in row]
with open('context/golden_ref.json') as f:
    gref = json.load(f)

# Let me simulate the RTL with the 1-cycle delay to confirm this is the issue.
def rtl_sim_delayed(pixels):
    """Simulate RTL with registered col_cnt (1-cycle delay)."""
    lb_rn2 = [0]*32
    lb_rn1 = [0]*32
    sr0 = [0,0,0]
    sr1 = [0,0,0]
    sr2 = [0,0,0]
    results = []
    pixel_cnt = 0
    col_cnt_reg = 0  # registered, lags by 1
    row_cnt_reg = 0
    pixel_in_reg = 0
    pixel_shift_reg = 0
    
    for idx, px in enumerate(pixels):
        px = int(px) & 0xFF
        # rx_valid for this pixel. The controller combinational outputs would be:
        cur_col = pixel_cnt % 32
        cur_row = pixel_cnt // 32
        
        # But in the current RTL, col_cnt is registered (from PREVIOUS cycle)
        # The line buffer and window use col_cnt_reg (the delayed value)
        active_col = col_cnt_reg
        active_row = row_cnt_reg
        active_shift = pixel_shift_reg
        active_pixel = pixel_in_reg
        
        # If pixel_shift_reg is 1 (from previous cycle's rx_valid):
        if active_shift:
            # Read line buffers at active_col (pre-edge)
            rn2 = lb_rn2[active_col] if active_row >= 2 else 0
            rn1 = lb_rn1[active_col] if active_row >= 1 else 0
            
            # Look-ahead window
            win = [sr0[1], sr0[2], rn2,
                   sr1[1], sr1[2], rn1,
                   sr2[1], sr2[2], active_pixel]
            
            # Check validity
            if active_col >= 2 and active_row >= 2:
                gx, gy, out = sobel_compute(win)
                results.append(out)
            
            # Update line buffers
            if active_row >= 1:
                lb_rn2[active_col] = lb_rn1[active_col]
            lb_rn1[active_col] = active_pixel
            
            # Update shift registers
            sr0 = sr0[1:] + [rn2]
            sr1 = sr1[1:] + [rn1]
            sr2 = sr2[1:] + [active_pixel]
        
        # Update registered outputs (at posedge)
        # Controller: if rx_valid, set col_cnt <= cur_col, etc.
        col_cnt_reg = cur_col
        row_cnt_reg = cur_row
        pixel_in_reg = px
        pixel_shift_reg = 1  # always 1 when rx_valid
        pixel_cnt += 1
    
    return results

results = rtl_sim_delayed(flat)
print("Delayed sim first 20:", results[:20])
print("Golden first 20:      ", gref[:20])

# Now simulate with combinational outputs (the fix)
def rtl_sim_combinational(pixels):
    """Simulate RTL with combinational col_cnt/pixel_in/pixel_shift."""
    lb_rn2 = [0]*32
    lb_rn1 = [0]*32
    sr0 = [0,0,0]
    sr1 = [0,0,0]
    sr2 = [0,0,0]
    results = []
    pixel_cnt = 0
    
    for idx, px in enumerate(pixels):
        px = int(px) & 0xFF
        # Combinational outputs (same cycle as rx_valid)
        col = pixel_cnt % 32
        row = pixel_cnt // 32
        
        # Read line buffers at col (pre-edge)
        rn2 = lb_rn2[col] if row >= 2 else 0
        rn1 = lb_rn1[col] if row >= 1 else 0
        
        # Look-ahead window
        win = [sr0[1], sr0[2], rn2,
               sr1[1], sr1[2], rn1,
               sr2[1], sr2[2], px]
        
        # Check validity
        if col >= 2 and row >= 2:
            gx, gy, out = sobel_compute(win)
            results.append(out)
        
        # Update line buffers (at posedge)
        if row >= 1:
            lb_rn2[col] = lb_rn1[col]
        lb_rn1[col] = px
        
        # Update shift registers (at posedge)
        sr0 = sr0[1:] + [rn2]
        sr1 = sr1[1:] + [rn1]
        sr2 = sr2[1:] + [px]
        
        pixel_cnt += 1
    
    return results

results2 = rtl_sim_combinational(flat)
print("Combinational sim first 20:", results2[:20])
print("Golden first 20:           ", gref[:20])
print("Full match?", results2 == gref)