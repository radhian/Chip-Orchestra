# Let me verify this approach with a simulation that models the combinational window.
# The window is assembled from the PRE-shift register values + new data (look-ahead).

import numpy as np

img = np.array([int(l.strip(),16) for l in open('rtl/sobel_input.mem') if l.strip()], 
               dtype=np.int32).reshape(32,32)

lb = [np.zeros(32, dtype=np.int32) for _ in range(2)]
sr0 = np.zeros(3, dtype=np.int32)  # row N-2
sr1 = np.zeros(3, dtype=np.int32)  # row N-1
sr2 = np.zeros(3, dtype=np.int32)  # row N

results = []

for r in range(32):
    for c in range(32):
        pixel = img[r, c]
        
        # Read BEFORE write (combinational read of line buffer)
        p_n2 = lb[r % 2][c]  # row N-2, col c
        p_n1 = lb[(r-1) % 2][c]  # row N-1, col c
        
        # Combinational window (look-ahead: what the window WILL BE after this shift)
        # New sr values: sr[0]<=sr[1], sr[1]<=sr[2], sr[2]<=new_data
        # New window: {sr0[1]_old, sr0[2]_old, p_n2, sr1[1]_old, sr1[2]_old, p_n1, sr2[1]_old, sr2[2]_old, pixel}
        w0 = sr0[1]; w1 = sr0[2]; w2 = p_n2
        w3 = sr1[1]; w4 = sr1[2]; w5 = p_n1
        w6 = sr2[1]; w7 = sr2[2]; w8 = pixel
        
        # Check window validity (combinational)
        if r >= 2 and c >= 2:
            gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
            gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
            mag = abs(gx) + abs(gy)
            results.append(min(mag, 255))
        
        # Update registers (on clock edge)
        sr0 = np.roll(sr0, -1); sr0[2] = p_n2
        sr1 = np.roll(sr1, -1); sr1[2] = p_n1
        sr2 = np.roll(sr2, -1); sr2[2] = pixel
        lb[r % 2][c] = pixel

results = np.array(results, dtype=np.uint8).reshape(30, 30)

with open('rtl/sobel_golden.mem') as f:
    golden = np.array([int(l.strip(),16) for l in f if l.strip()], dtype=np.uint8).reshape(30,30)

print("Match:", np.array_equal(results, golden))
print("Max diff:", int(np.max(np.abs(results.astype(int) - golden.astype(int)))))
print("Num results:", len(results.ravel()))
print("First row:", results[0,:5])
print("Golden row:", golden[0,:5])