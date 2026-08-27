# The pixel-dropping hypothesis gives 464 results, not 900. And the values don't match.
# So that's not the issue. The chip produces 900 results, and even indices match golden.
#
# Let me look at this more carefully. The chip produces 900 values. Even indices match
# golden exactly. Odd indices are wrong. The odd values are ~0x9c-0x9f (156-159).
#
# Let me check: what if the UART TX is sending TWO bytes per result - the correct
# result followed by a garbage byte? Or what if the tb is capturing an extra byte?
#
# Actually, let me look at the chip_output.mem more carefully. It has 957 lines
# but 900 values (plus comment lines every 16 entries). Let me check if there
# are comment lines interspersed.

with open('waves/chip_output.mem') as f:
    lines = f.readlines()
print("Total lines:", len(lines))
comments = [i for i, l in enumerate(lines) if l.strip().startswith('//')]
print("Comment lines at:", comments[:10])
print("Comment count:", len(comments))
vals = [int(l.strip(),16) for l in lines if l.strip() and not l.startswith('//')]
print("Value count:", len(vals))

# So 900 values, 57 comments. 900+57=957. OK.
# The comments are $writememh address markers every 16 values.
# So the file is fine - 900 values.

# Now, the key question: why do even indices match and odd don't?
# The tb captures bytes from UART TX. Each capture is one byte.
# chip_out[0] = first captured byte, chip_out[1] = second, etc.
#
# If the controller sends 900 correct results, but the tb captures
# 900 bytes where every other one is wrong... that means the tb is
# receiving extra bytes between the correct ones.
#
# OR: the controller is sending 1800 bytes (2 per result), and the tb
# captures all 1800, but only 900 fit in the array.
#
# Wait, the tb captures exactly N_RESULTS=900 bytes. If the controller
# sends more, the extra ones are lost.
#
# Let me check: what if the controller sends the result byte, and then
# ALSO sends another byte (the pixel value or a stale result)?
# The tb would capture both, storing them alternately.
# chip[0] = result[0] (correct), chip[1] = extra byte, chip[2] = result[1], etc.
#
# This would explain the pattern! Even indices = correct results,
# odd indices = extra/garbage bytes.
#
# What could cause the controller to send extra bytes?
# Looking at the controller FSM:
# S_TX_RESULT: tx_start=1, go to S_NEXT (1 cycle)
# S_NEXT: wait for tx_done, then go to S_RECV or S_IDLE
#
# tx_start is a registered output. It's set to 1 in S_TX_RESULT and
# defaulted to 0 otherwise. So it should only pulse once per result.
#
# But wait - the UART TX latches tx_start on ANY clock, not just baud ticks.
# If tx_start is high for 1 cycle, the UART TX latches it. That's fine.
#
# Hmm, but what if the controller re-enters S_TX_RESULT unexpectedly?
# Let me check: after S_TX_RESULT -> S_NEXT -> (tx_done) -> S_RECV.
# In S_RECV, if rx_valid and row>=2 && col>=2, it captures and goes to S_TX_RESULT again.
# This is normal - one TX per result.
#
# Let me look at the actual simulation log for clues.
print("\n--- Checking sim log ---")