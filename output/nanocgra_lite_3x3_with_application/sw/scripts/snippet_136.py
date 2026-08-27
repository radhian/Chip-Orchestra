import json
# vec 37 is a discrepancy in the vector file itself (golden model disagrees with its own vectors).
# The instructions say: "the numbers in the vectors file are the contract; never round, rescale or 'fix' them."
# So the TB must check against the vector file's expected values, NOT the golden model.
# But the RTL (line_buffer.v) with shift_en=0 will NOT shift, so it will produce [5..36], NOT [0..0,42].
# This means the RTL will FAIL vec 37. That's a real bug the TB should catch.
# 
# Wait — let me re-read. The vector says shift_en=0, pixel_in=99, but expected row=[0..0,42].
# That looks like the vector was generated with shift_en=1, pixel_in=42 (one shift of 42 into a zeroed buffer).
# Actually [0..0,42] is what you get if you reset then shift in 42 once. 
# This is likely a vector-file generation bug. But per instructions, the vectors are the contract.
# 
# However, the RTL line_buffer with the given inputs (shift_en=0) will produce [5..36].
# So this vector WILL fail. The instructions say to $fatal on mismatch and display the failing vector.
# That's exactly what we should do — the TB catches the discrepancy.
#
# Actually, let me reconsider. Maybe the vector generation used a FRESH line_buffer for vec 37
# (not continuing from vec 36). Let me check: if we reset and do step(1,1,0,99) -> row stays [0..0].
# That gives [0..0], not [0..0,42]. 
# If we reset and do step(1,1,1,42) -> row=[0..0,42]. That matches!
# So vec 37's inputs say shift_en=0,pixel_in=99 but the expected matches shift_en=1,pixel_in=42.
# This is a vector file bug. 
#
# The instructions are clear: bake the vectors as-is. The TB will catch this as a failure.
# But actually — will the compile-check pass? Yes, compile is separate from sim.
# The TB compiles clean, and when run, vec 37 fails with $fatal. That's correct behavior
# for a self-checking TB — it reports the mismatch.
#
# Let me proceed: bake all vectors exactly as they are.

# Let me verify the RTL line_buffer behavior matches the golden model for the OTHER vectors
# by checking the RTL semantics. The RTL: shift_en shifts left, pushes pixel_in at right.
# Golden model: row = row[1:] + [pixel_in]. Same. Good.
# vec 37 will fail in both RTL and golden-model-vs-vectors. That's a vector file issue,
# but our job is to write the TB per the contract.

print("Understood: vec 37 is a vector-file discrepancy. TB will catch it. Proceeding.")