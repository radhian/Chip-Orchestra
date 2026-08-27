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
with open('context/golden_ref.json') as f:
    gref = json.load(f)

# My simulations don't match the actual chip output. The actual chip has a very specific
# alternating pattern. Let me think about what could cause this.
# 
# chip: 72, 158, 60, 161, 66, 161, 64, 161, 66, 158, 66, 161, 66, 158, 60, 159, 64, 159, 62, 160
# Even: 72, 60, 66, 64, 66, 66, 66, 60, 64, 62
# Odd:  158, 161, 161, 161, 158, 161, 158, 159, 159, 160
#
# Golden: 68, 56, 58, 60, 62, 60, 62, 60, 60, 58, 60, 60, 60, 58, 58, 60, 60, 58, 62, 62
# Even: 68, 58, 62, 62, 60, 60, 60, 58, 60, 62
# Odd:  56, 60, 60, 60, 58, 60, 58, 60, 58, 62
#
# The even chip values are close to golden even values (off by 2-4).
# The odd chip values are ~160 (way off from golden ~58-60).
#
# 160 = 0xa0. This is suspicious - it's 128 + 32. Or it could be a specific sobel result.
# Let me check what window gives 161.
# 
# Actually, let me think about the line buffer read timing more carefully.
# The line buffer rd_data is combinational: assign rd_data = mem[rd_col[4:0]];
# rd_col is connected to col_cnt (registered output of controller).
# 
# At the posedge where rx_valid=1:
# - Controller: col_cnt <= cur_col (non-blocking, takes effect at end of timestep)
# - Line buffer: mem[wr_col] <= pixel_in (non-blocking, wr_col=col_cnt=OLD value)
# - Window: win is combinational, uses lb_rn2_rd and lb_rn1_rd
#   - lb_rn2_rd = mem[col_cnt] = mem[OLD col_cnt] (combinational, before edge)
#   - lb_rn1_rd = mem[col_cnt] = mem[OLD col_cnt] (combinational, before edge)
# - sobel_out is combinational from win
# - Controller captures sobel_out: result_reg <= sobel_out (non-blocking, captures pre-edge value)
#
# So the captured sobel_out uses:
# - win from sr registers (pre-edge) + lb_data at OLD col_cnt + pixel_in (rx_byte)
# - The window is the look-ahead: {sr0_1, sr0_2, lb_rn2_rd, sr1_1, sr1_2, lb_rn1_rd, sr2_1, sr2_2, rx_byte}
# - lb_rn2_rd and lb_rn1_rd are at OLD col_cnt (previous pixel's column)
# - But the validity check uses cur_col/cur_row (current pixel's position)
#
# So when the controller decides to emit (cur_col >= 2, cur_row >= 2),
# the window uses lb data from the PREVIOUS column (col_cnt_reg = previous col).
# This means the window is shifted by one column!
#
# For even output indices (col 2, 4, 6, ...): the window uses lb data from col 1, 3, 5, ...
# For odd output indices (col 3, 5, 7, ...): the window uses lb data from col 2, 4, 6, ...
#
# This shift would cause every other output to be wrong.
# But my simulation with this mismatch didn't produce the right pattern.
# 
# Let me try a more precise simulation that accounts for the EXACT RTL behavior,
# including the fact that pixel_shift is also delayed.

def rtl_sim_precise(pixels):
    """Precise RTL simulation with all registered outputs delayed by 1 cycle."""
    # Line buffers (column-addressed)
    lb_rn1 = [0]*32  # row N-1
    lb_rn2 = [0]*32  # row N-2
    # Window shift registers
    sr0 = [0,0,0]
    sr1 = [0,0,0]
    sr2 = [0,0,0]
    results = []
    
    # Registered outputs (delayed by 1 cycle)
    pixel_cnt = 0
    col_cnt_r = 0
    row_cnt_r = 0
    pixel_in_r = 0
    pixel_shift_r = 0
    state = 0  # 0=IDLE, 1=RECV, 2=TX_RESULT, 3=NEXT
    
    # We need to model the UART RX timing. rx_valid fires once per byte.
    # The TB sends bytes one at a time. Between bytes, there are gaps.
    # Let's model rx_valid as a pulse that happens once per "byte time".
    
    # Actually, the key issue is simpler. Let me model cycle-by-cycle.
    # Each "pixel" in the loop = one rx_valid pulse.
    # Between rx_valid pulses, there are many idle cycles (UART byte time).
    # During idle cycles, pixel_shift_r = 0 (default), so nothing happens.
    
    # When rx_valid fires (cycle T):
    #   Controller (combinational): cur_col = pixel_cnt%32, cur_row = pixel_cnt//32
    #   If state == RECV and cur_row>=2 and cur_col>=2:
    #     result_reg <= sobel_out (pre-edge value)
    #     state <= TX_RESULT
    #   At posedge: col_cnt_r <= cur_col, row_cnt_r <= cur_row, pixel_in_r <= rx_byte,
    #               pixel_shift_r <= 1, pixel_cnt <= pixel_cnt+1
    #
    # Cycle T+1 (pixel_shift_r = 1, col_cnt_r = cur_col from pixel at T):
    #   Line buffer: mem[col_cnt_r] <= pixel_in_r (writes at cur_col of pixel T)
    #   Window: shifts, using lb data at col_cnt_r = cur_col of pixel T
    #   But sobel_out was already captured at cycle T using OLD col_cnt_r!
    
    # Wait, I need to be more careful. The line buffer and window update at the posedge.
    # At posedge T (rx_valid=1):
    #   Non-blocking assignments execute:
    #   - Controller: col_cnt_r <= cur_col, pixel_shift_r <= 1, pixel_in_r <= rx_byte, pixel_cnt <= pixel_cnt+1
    #   - Line buffer: mem[wr_col] <= pixel_in, where wr_col = col_cnt_r (OLD value, before update)
    #     and pixel_in = pixel_in_r (OLD value) -- wait, pixel_in is the controller's output.
    #     The line buffer's pixel_in port is connected to the controller's pixel_in output.
    #     At posedge T, pixel_in_r is being updated to rx_byte (non-blocking).
    #     The line buffer's always block uses pixel_in (the wire), which = pixel_in_r.
    #     Since pixel_in_r is non-blocking, the line buffer sees the OLD pixel_in_r.
    #   - Window: sr registers shift, using lb0_data and lb1_data (combinational reads of mem at OLD col_cnt_r)
    #     and pixel_in (OLD pixel_in_r)
    #
    # So at posedge T:
    #   - Line buffer writes OLD pixel_in_r at OLD col_cnt_r
    #   - Window shifts in OLD lb data at OLD col_cnt_r and OLD pixel_in_r
    #   - Controller captures sobel_out (combinational, uses pre-edge win = OLD sr + OLD lb + OLD pixel_in)
    #   - Controller updates col_cnt_r to cur_col, pixel_in_r to rx_byte, pixel_shift_r to 1
    #
    # At posedge T+1 (no rx_valid, pixel_shift_r = 1 from T):
    #   - Line buffer writes pixel_in_r (= rx_byte from T) at col_cnt_r (= cur_col from T)
    #   - Window shifts in lb data at col_cnt_r (= cur_col from T) and pixel_in_r (= rx_byte from T)
    #   - pixel_shift_r <= 0 (default)
    #
    # So the line buffer write and window shift happen at T+1, not T!
    # The controller captures sobel_out at T using the OLD window (from T-1's shift).
    #
    # This means:
    # - At cycle T (rx_valid for pixel k):
    #   - sobel_out = f(window after T-1's shift) = f(window using pixel k-1's data)
    #   - Controller captures this if cur_col >= 2 and cur_row >= 2
    #   - cur_col = pixel_cnt % 32 = k % 32 (before increment)
    # - At cycle T+1:
    #   - Line buffer writes pixel k at col k%32
    #   - Window shifts in pixel k's data
    #
    # So the captured sobel_out is from the window that was built with pixel k-1's data,
    # but the validity check uses pixel k's position. This is a 1-pixel mismatch!
    #
    # The window at cycle T reflects the state after processing pixel k-1.
    # The validity check says "pixel k is at (row, col) >= (2, 2)".
    # But the window is for pixel k-1's position.
    #
    # When k=66 (row=2, col=2): validity check passes (2>=2, 2>=2).
    # The window is from pixel 65 (row=2, col=1). The window has cols -1, 0, 1 of rows 0, 1, 2.
    # But col -1 doesn't exist, so it's 0 or garbage. This gives a wrong result.
    #
    # When k=67 (row=2, col=3): validity check passes.
    # The window is from pixel 66 (row=2, col=2). The window has cols 0, 1, 2 of rows 0, 1, 2.
    # This is the CORRECT first window! So the result should be golden[0].
    #
    # So the chip output is shifted by 1: chip[0] corresponds to golden[-1] (invalid),
    # chip[1] corresponds to golden[0], chip[2] to golden[1], etc.
    # But the chip has 900 values, and golden has 900. So the last one is missing or extra.
    #
    # Let me check: chip[1] should be golden[0]=68. But chip[1]=158. Doesn't match!
    # So my theory is wrong, or there's an additional issue.
    
    # Let me try yet another approach: simulate the EXACT cycle-by-cycle behavior.
    # I'll model each clock cycle, tracking when rx_valid fires.
    
    # For simplicity, assume rx_valid fires on consecutive cycles (no gaps).
    # This isn't realistic (UART has byte-time gaps) but let's see if the pattern matches.
    
    # Actually, the gaps don't matter because pixel_shift_r=0 during gaps (no shifting).
    # The key is what happens on the cycle of rx_valid and the next cycle.
    
    # Let me model it as: each iteration = one rx_valid cycle + one shift cycle.
    lb_rn1 = [0]*32
    lb_rn2 = [0]*32
    sr0 = [0,0,0]
    sr1 = [0,0,0]
    sr2 = [0,0,0]
    results = []
    pixel_cnt = 0
    col_cnt_r = 0
    row_cnt_r = 0
    pixel_in_r = 0
    pixel_shift_r = 0
    state = 0  # IDLE
    result_reg = 0
    out_cnt = 0
    tx_busy = False  # simplified
    
    rx_valid = 0
    rx_byte = 0
    
    for cycle in range(10000):
        if cycle % 2 == 0 and pixel_cnt < 1024 and state in [0, 1]:
            rx_valid = 1
            rx_byte = flat[pixel_cnt]
        else:
            rx_valid = 0
        
        # Combinational outputs
        cur_col = pixel_cnt % 32
        cur_row = pixel_cnt // 32
        
        # Line buffer reads (combinational, using registered col_cnt_r)
        rn2_rd = lb_rn2[col_cnt_r % 32] if row_cnt_r >= 2 else 0
        rn1_rd = lb_rn1[col_cnt_r % 32] if row_cnt_r >= 1 else 0
        
        # Window (combinational look-ahead)
        win = [sr0[1], sr0[2], rn2_rd,
               sr1[1], sr1[2], rn1_rd,
               sr2[1], sr2[2], pixel_in_r]
        
        # Sobel
        sobel_val = 0
        if col_cnt_r >= 2 and row_cnt_r >= 2:
            _, _, sobel_val = sobel_compute(win)
        
        # Controller logic (at posedge)
        new_pixel_shift = 0
        new_col_cnt = col_cnt_r
        new_row_cnt = row_cnt_r
        new_pixel_in = pixel_in_r
        new_pixel_cnt = pixel_cnt
        new_state = state
        new_result = result_reg
        
        if state == 0:  # IDLE
            if rx_valid:
                new_pixel_in = rx_byte
                new_pixel_shift = 1
                new_col_cnt = cur_col
                new_row_cnt = cur_row
                new_pixel_cnt = pixel_cnt + 1
                new_state = 1
        elif state == 1:  # RECV
            if rx_valid:
                new_pixel_in = rx_byte
                new_pixel_shift = 1
                new_col_cnt = cur_col
                new_row_cnt = cur_row
                new_pixel_cnt = pixel_cnt + 1
                if cur_row >= 2 and cur_col >= 2:
                    new_result = sobel_val  # capture pre-edge sobel_out
                    new_state = 2  # TX_RESULT
        elif state == 2:  # TX_RESULT
            new_state = 3  # NEXT
        elif state == 3:  # NEXT
            # Simplified: immediately done
            out_cnt += 1
            if out_cnt >= 900:
                new_state = 0
            else:
                new_state = 1
        
        # Line buffer and window updates (at posedge, using registered values)
        if pixel_shift_r:
            col = col_cnt_r % 32
            row_w = row_cnt_r
            # Read pre-edge values for window shift
            rn2_pre = lb_rn2[col] if row_w >= 2 else 0
            rn1_pre = lb_rn1[col] if row_w >= 1 else 0
            # Update line buffers
            if row_w >= 1:
                lb_rn2[col] = lb_rn1[col]
            lb_rn1[col] = pixel_in_r
            # Update window shift registers
            sr0 = sr0[1:] + [rn2_pre]
            sr1 = sr1[1:] + [rn1_pre]
            sr2 = sr2[1:] + [pixel_in_r]
        
        # Capture result
        if state == 1 and rx_valid and cur_row >= 2 and cur_col >= 2:
            results.append(sobel_val)
        
        # Update registered values
        col_cnt_r = new_col_cnt
        row_cnt_r = new_row_cnt
        pixel_in_r = new_pixel_in
        pixel_shift_r = new_pixel_shift
        pixel_cnt = new_pixel_cnt
        state = new_state
        result_reg = new_result
        
        if len(results) >= 20:
            break
    
    print("Precise sim first 20:", results[:20])
    print("Chip first 20:        ", cmem[:20])
    print("Match?", results[:20] == cmem[:20])