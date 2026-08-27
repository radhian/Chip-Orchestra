import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]
IMG_W = 32

def sobel_compute(win):
    w = [int(x) & 0xFF for x in win]
    gx = (-w[0] + w[2] - 2*w[3] + 2*w[5] - w[6] + w[8])
    gy = (-w[0] - 2*w[1] - w[2] + w[6] + 2*w[7] + w[8])
    mag = abs(gx) + abs(gy)
    out = max(0, min(255, mag))
    return gx, gy, out

# 156 doesn't come from any nearby 3x3 window. The chip value 0x9c=156 is strange.
# Let me check: maybe the chip is computing on a completely wrong window.
# 
# Let me look at the chip values more carefully.
# chip out[0] = 0x44 = 68 (matches golden)
# chip out[1] = 0x9c = 156
# chip out[2] = 0x3a = 58 (matches golden)
# chip out[3] = 0x9e = 158
#
# The even outputs match. The odd outputs are ~100 higher.
# 156 - 56 = 100, 158 - 60 = 98, 157 - 58 = 99, 159 - 62 = 97
# These differences are close to 100 but not exact.
#
# What if the chip is adding an extra pixel value to the Sobel result?
# Or what if the window has an extra pixel that shouldn't be there?
#
# Let me check: what if on odd columns, the chip uses a 3x3 window that includes
# a pixel from the WRONG column — like the center column is shifted?
#
# Actually, let me look at this differently. The chip out[1] = 0x9c = 156.
# The golden out[1] = 0x38 = 56. The difference is 100.
# 
# What if the chip's window for odd columns has the line buffer values shifted
# by one column? i.e., the shift register didn't shift properly.
#
# Let me try: what if sr0_1 and sr0_2 are swapped, or the shift is wrong?
# For out[1] (col=3), the correct window row N-2 = [155, 155, 155] (cols 1,2,3)
# What if the shift register gives [151, 155, 155] (cols 0,1,2) — i.e., it didn't shift?
win_noshift = [151, 155, 155, 165, 167, 167, 167, 169, 169]
print("no shift (cols 0,1,2):", hex(sobel_compute(win_noshift)[2]))
# That's 0x44 = 68, same as out[0]. Not 156.

# What if the shift register shifted TWICE? cols 2,3,4
win_dblshift = [155, 155, 155, 167, 167, 167, 169, 169, 170]
print("double shift (cols 2,3,4):", hex(sobel_compute(win_dblshift)[2]))
# That's 0x3a = 58, same as out[2]. Not 156.

# Hmm. 156 is not a simple Sobel of any nearby window. Let me think about what
# could produce 156.
# 156 = |gx| + |gy|. Possible: gx=100, gy=56 or gx=156, gy=0, etc.
# 
# What if the chip is adding the pixel value to the Sobel result?
# out[1] golden = 56. If we add pixel_in = pixels[67] = 169... 56+169 = 225. No.
# If we add the center pixel: pixels[66] = 169. 56+169 = 225. No.
#
# What if there's a signedness issue? 0x9c = 156 as unsigned, but as signed = -100.
# The golden is 0x38 = 56. 56 + 100 = 156. And -100 + 256 = 156.
# So the chip might be computing -100 instead of 56, which wraps to 156.
# But Sobel magnitude should never be negative...
#
# Unless the saturation is wrong. What if mag > 255 wraps instead of saturating?
# Or what if the abs computation is wrong?
#
# Let me check: what if abs_gx is computed wrong for negative gx?
# In the RTL: abs_gx = (gx < 0) ? -gx : gx
# gx is signed [10:0]. If gx = -100, abs_gx = 100. That's correct.
# But what if gx overflows the 11-bit signed range?
# gx range: -510..+510. 11-bit signed: -1024..+1023. So no overflow. ✓
#
# What if the issue is in the magnitude addition?
# mag = abs_gx + abs_gy. Both are signed [10:0] (0..510).
# mag is wire [10:0] (unsigned). abs_gx + abs_gy could be up to 1020.
# 1020 in 11 bits = 1020 < 2048. ✓
# But wait — abs_gx and abs_gy are SIGNED [10:0]. Adding two signed values...
# In Verilog, abs_gx + abs_gy where both are signed [10:0]...
# The result is signed [10:0] but mag is unsigned [10:0].
# Actually, the addition is fine because the values are non-negative.
#
# Let me check the saturation: if (mag > 11'd255) sobel_out = 8'd255; else sobel_out = mag[7:0]
# mag is [10:0]. 11'd255 = 0FF. mag > 255 checks bits 10:8. If any of those are 1, mag > 255.
# mag[7:0] gives the low 8 bits. This looks correct.
#
# Hmm, but what if mag is computed as SIGNED and the comparison is wrong?
# wire [10:0] mag = abs_gx + abs_gy;
# abs_gx and abs_gy are wire signed [10:0]. The sum is assigned to wire [10:0] mag (unsigned).
# In Verilog, if the RHS is signed and the LHS is unsigned, the result is treated as unsigned.
# The addition itself: abs_gx + abs_gy. Both are signed, so the addition is signed.
# But the values are non-negative (0..510), so the signed addition gives the correct result.
# The result is then stored in mag (unsigned [10:0]). ✓
#
# I'm stuck on the datapath. Let me add debug output to the RTL to see the actual
# window and sobel values.

# Actually, let me check if the issue is in the controller's timing — maybe it's
# capturing the WRONG sobel_out value. The sobel_out is combinational based on win.
# win is combinational based on the shift registers and line buffers.
# The controller captures sobel_out when rx_valid && row>=2 && col>=2.
# But at that moment, the shift registers haven't shifted yet (they shift on the edge).
# The combinational win shows the POST-shift window (look-ahead).
# 
# But what if the look-ahead is wrong? Let me re-examine.
# win = {sr0_1, sr0_2, lb0_data, sr1_1, sr1_2, lb1_data, sr2_1, sr2_2, pixel_in}
# This is the POST-shift window: (old sr0_1, old sr0_2, lb0_data)
# After shift: new sr0_0 = old sr0_1, new sr0_1 = old sr0_2, new sr0_2 = lb0_data
# So the window columns are: (new sr0_0, new sr0_1, new sr0_2) = (old sr0_1, old sr0_2, lb0_data) ✓
#
# But the controller captures sobel_out on the SAME cycle as rx_valid.
# At this cycle, the shift registers have the PRE-shift values.
# The combinational win shows the POST-shift values. ✓
# The controller captures this value. On the NEXT cycle, the shift registers have shifted.
# So the captured value corresponds to the POST-shift window. ✓
#
# This all seems correct. Let me just add debug and run.

print("Going to add debug output to see actual window values")