import json, sys
sys.path.insert(0, '.')
from golden.model.sobel_core import sobel_compute

with open('context/chip_input_grid.json') as f:
    g = json.load(f)
px = g['pixels']
flat = [p for row in px for p in row]
with open('context/golden_ref.json') as f:
    gref = json.load(f)

# The fixed sim is off by one - it produces 255 at index 0, then matches from index 1.
# The 255 is an extra result. The issue is the col/row used for the validity check.
# In the golden functional model:
#   row = idx // 32, col = idx % 32  (idx is 0-based, BEFORE increment)
#   if col >= 2 and row >= 2: emit
# In my fixed sim, I use the POST-increment col/row.
# The golden controller uses POST-increment col/row for the check too.
# But the golden functional model uses the ORIGINAL idx (pre-increment).
# 
# Wait, let me re-read sobel_stream:
#   for idx, px in enumerate(pixels):
#       row = idx // IMG_W
#       col = idx % IMG_W
#       ... 
#       if col >= 2 and row >= 2: emit
# So idx is 0-based. The first pixel is idx=0 (row=0, col=0). The first valid window is
# at idx = 2*32+2 = 66 (row=2, col=2). That's the 67th pixel (0-indexed).
# 
# In the golden controller, _accept_pixel increments pixel_cnt FIRST:
#   pixel_cnt += 1  (now pixel_cnt = 1 for first pixel)
#   col_cnt = pixel_cnt % 32 = 1
#   row_cnt = pixel_cnt // 32 = 0
# Then checks row_cnt >= 2 and col_cnt >= 2.
# For the first pixel: pixel_cnt=1, col=1, row=0. No emit.
# For pixel at idx=66 (67th pixel): pixel_cnt=67, col=67%32=3, row=67//32=2.
#   row=2, col=3. col >= 2, row >= 2. EMIT.
# But the golden functional model emits at idx=66 (row=2, col=2), not idx=67.
# 
# So the controller is OFF BY ONE from the functional model!
# The controller increments pixel_cnt BEFORE setting col/row, so col_cnt is one ahead.
# The functional model uses idx (0-based, pre-increment).
#
# This means the controller captures sobel_out one pixel too late.
# The first result should be at pixel idx=66 (row=2, col=2), but the controller
# emits at pixel_cnt=67 (row=2, col=3).
#
# But wait - the golden model's controller ALSO does this (pixel_cnt += 1 before col_cnt).
# And the TB compares against sobel_stream (the functional model).
# So either the controller golden model is wrong, or the functional model is the truth
# and the controller must match it.
#
# The instructions say: "the golden model decides which is wrong" and "the golden model 
# and the canonical input are the truth". The TB uses sobel_stream for the golden output.
# So the RTL must match sobel_stream.
#
# sobel_stream emits at idx where col>=2 and row>=2 (idx=66 is first).
# The controller should emit when the window for (row=2, col=2) is complete.
# That happens when pixel idx=66 is received (the BR pixel of the window).
# At that point, pixel_cnt should be 66 (0-indexed count of pixels received so far, 
# BEFORE this one) or 67 (after increment)?
#
# In sobel_stream, idx=66 means we've received 67 pixels (0..66). The window at (2,2)
# uses pixels at rows 1,2,3 and cols 1,2,3. The last pixel needed is (3,3) = idx 99.
# Wait no - the window centered at (2,2) uses (1,1)..(3,3). The last pixel is (3,3)=idx 99.
# But sobel_stream emits at idx=66 which is (2,2). That's the CENTER pixel, not the BR.
#
# Hmm, let me re-read sobel_stream more carefully.
# The window is built from wcols which accumulates the last 3 columns.
# At idx=66 (row=2, col=2): wcols has been shifting. The window is:
#   wcols[0] = [col0, col1, col2] of row N-2 = row 0
#   wcols[1] = [col0, col1, col2] of row N-1 = row 1
#   wcols[2] = [col0, col1, col2] of row N = row 2
# So the window is rows 0,1,2 and cols 0,1,2. That's the TL 3x3 block.
# The first output is the Sobel of the top-left 3x3 window. Makes sense.
# The last pixel needed for this window is (2,2) = idx 66. Correct.
#
# So the controller should emit when pixel idx=66 is received.
# In the controller, pixel_cnt starts at 0. After _accept_pixel for idx=0: pixel_cnt=1.
# After _accept_pixel for idx=66: pixel_cnt=67. col_cnt=67%32=3, row_cnt=67//32=2.
# The check is row_cnt>=2 && col_cnt>=2: 2>=2 && 3>=2 = true. EMIT.
# But the functional model emits at idx=66 (col=2, row=2), not idx=67 (col=3, row=2).
# 
# So the controller emits one pixel too late! The window at idx=67 is cols 1,2,3 of rows 0,1,2.
# But the golden emits the window at cols 0,1,2 of rows 0,1,2 (idx=66).
#
# The fix: the controller should check the PRE-increment col/row, not post-increment.
# OR: don't increment pixel_cnt before setting col/row.
# 
# Actually, looking at the golden controller again:
#   def _accept_pixel(self, byte):
#       self.pixel_in = int(byte) & 0xFF
#       self.pixel_shift = 1
#       self.pixel_cnt += 1
#       self.col_cnt = self.pixel_cnt % IMG_W
#       self.row_cnt = self.pixel_cnt // IMG_W
# This sets col_cnt/row_cnt to the POST-increment value. Then the check uses these.
# For idx=66: pixel_cnt becomes 67, col_cnt=3, row_cnt=2. Check passes.
# But the window that was just built is for col=2 (the current pixel's column).
# The sobel_out is computed from the window which uses col_cnt for the line buffer tap.
# If col_cnt=3, the line buffer is tapped at col 3, but the current pixel is at col 2.
# So the window gets the WRONG column data!
#
# The fundamental issue: the controller sets col_cnt to (pixel_cnt+1)%32 but the current
# pixel is at column (pixel_cnt)%32 = pixel_cnt-1 after increment. Wait, no.
# If pixel_cnt was 66 before _accept_pixel, after increment it's 67.
# col_cnt = 67 % 32 = 3. But the pixel just received is idx=66, which is col=66%32=2.
# So col_cnt=3 but the pixel is at col 2. The col_cnt is ONE AHEAD.
#
# The fix: set col_cnt = (pixel_cnt-1) % 32 after increment, or don't increment first.
# Or: set col_cnt = pixel_cnt % 32 BEFORE incrementing.
# 
# In the golden functional model: col = idx % 32 where idx is the current pixel index.
# So col_cnt should be the index of the current pixel, not the next one.
# 
# The fix for the controller: 
#   col_cnt = pixel_cnt % 32  (BEFORE increment)
#   row_cnt = pixel_cnt // 32 (BEFORE increment)
#   pixel_cnt += 1
# OR equivalently:
#   pixel_cnt += 1
#   col_cnt = (pixel_cnt - 1) % 32
#   row_cnt = (pixel_cnt - 1) // 32

# Let me verify with the corrected controller timing.
def fixed_rtl_sim_v2(pixels):
    """Fixed RTL with corrected controller timing."""
    lb_rn2 = [0]*32
    lb_rn1 = [0]*32
    sr0 = [0,0,0]
    sr1 = [0,0,0]
    sr2 = [0,0,0]
    results = []
    pixel_cnt = 0  # count of pixels received so far (before current)
    
    for idx, px_in in enumerate(pixels):
        px_in = int(px_in) & 0xFF
        # Current pixel is at (row, col) = (idx//32, idx%32)
        col = idx % 32
        row = idx // 32
        
        # Read line buffers at col (PRE-edge values)
        rn2 = lb_rn2[col] if row >= 2 else 0
        rn1 = lb_rn1[col] if row >= 1 else 0
        
        # Look-ahead window
        win = [sr0[1], sr0[2], rn2,
               sr1[1], sr1[2], rn1,
               sr2[1], sr2[2], px_in]
        
        # Check validity using CURRENT col/row (not incremented)
        if col >= 2 and row >= 2:
            gx, gy, out = sobel_compute(win)
            results.append(out)
        
        # Update line buffers
        if row >= 1:
            lb_rn2[col] = lb_rn1[col]
        lb_rn1[col] = px_in
        
        # Update window shift registers
        sr0 = sr0[1:] + [rn2]
        sr1 = sr1[1:] + [rn1]
        sr2 = sr2[1:] + [px_in]
        
        pixel_cnt += 1
    
    return results

results = fixed_rtl_sim_v2(flat)
print("Fixed v2 first 20:", results[:20])
print("Golden first 20:   ", gref[:20])
print("Full match?", results == gref)