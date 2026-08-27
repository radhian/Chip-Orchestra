# Let me revert my change and think differently. The issue is clearly a 
# column-parity problem (odd columns mismatch). Let me look at the window_3x3
# shift register logic more carefully.
#
# The window_3x3 has 3-deep column shift registers: sr0_0, sr0_1, sr0_2
# win = {sr0_1, sr0_2, lb0_data, ...}  (look-ahead: post-shift values)
# On shift: sr0_0 <= sr0_1, sr0_1 <= sr0_2, sr0_2 <= lb0_data
#
# So after shift at col c:
#   new sr0_0 = old sr0_1 (col c-2 value)
#   new sr0_1 = old sr0_2 (col c-1 value)  
#   new sr0_2 = lb0_data (col c value)
# And win shows: (old sr0_1, old sr0_2, lb0_data) = (col c-2, col c-1, col c) ✓
#
# This is correct. But wait — the win is COMBINATIONAL and uses the PRE-shift
# register values. The controller captures sobel_out (based on win) on the same
# cycle as rx_valid. At that cycle, pixel_shift=1, so the registers will shift
# on the clock edge. The combinational win shows the post-shift window. ✓
#
# But here's the key: the line buffers ALSO update on the same edge.
# lb_rn1[col] <= pixel_in, lb_rn2[col] <= lb_rn1_rd
# The window reads lb0_data = lb_rn2_rd (pre-edge) and lb1_data = lb_rn1_rd (pre-edge)
# These are the values BEFORE the line buffer update. ✓
#
# So for the window at col c:
#   row N-2 = lb_rn2[col c] (pre-edge) = the pixel from row N-2 at col c
#   row N-1 = lb_rn1[col c] (pre-edge) = the pixel from row N-1 at col c
#   row N = pixel_in = current pixel at col c
#
# And the shift registers hold cols c-2 and c-1 for each row.
# This all seems correct.
#
# Let me check if there's an issue with the line buffer read at col_cnt.
# The line_buffer reads combinationally: assign rd_data = mem[rd_col[4:0]];
# rd_col = col_cnt = cur_col = pixel_cnt[4:0]
# This is the PRE-increment column. ✓
#
# Wait — I need to check the line buffer write more carefully.
# lb_rn1 writes pixel_in at wr_col=col_cnt on pixel_shift.
# But col_cnt is combinational (pixel_cnt[4:0]). When pixel_cnt increments
# on the clock edge, col_cnt changes. But the write uses the pre-edge col_cnt. ✓
#
# Hmm, let me check if the issue is that the line buffer for lb_rn2 is reading
# lb_rn1_rd which is the combinational read of lb_rn1 at col_cnt. But lb_rn1
# is ALSO being written at col_cnt on the same edge. The combinational read
# returns the pre-edge value. The write updates it. So lb_rn2 gets the old
# lb_rn1 value. ✓
#
# OK, I'm going in circles. Let me just add some debug output to the RTL
# and see what window values the chip actually computes.
# Actually, let me check the sobel_input.mem file — maybe it doesn't match
# the canonical input.

import json
with open('context/chip_input_grid.json') as f:
    g = json.load(f)
pixels = [p for row in g['pixels'] for p in row]

# Read sobel_input.mem
def load_mem(path):
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            for tok in line.split():
                if tok.startswith('//'): break
                vals.append(int(tok, 16))
    return vals

input_mem = load_mem('rtl/sobel_input.mem')
print("input_mem len:", len(input_mem))
print("input_mem first 10:", input_mem[:10])
print("canonical first 10:", pixels[:10])
print("match:", input_mem[:10] == pixels[:10])

# Check full match
match = all(input_mem[i] == pixels[i] for i in range(min(len(input_mem), len(pixels))))
print("full match:", match, "lens:", len(input_mem), len(pixels))