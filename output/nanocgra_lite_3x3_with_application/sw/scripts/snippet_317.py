# The golden tests pass (52 passed). But the golden model uses a different
# simulation approach than the Verilog testbench.
# 
# The key issue: the Verilog testbench was passing BEFORE my change to uart_tx.v.
# My change to the STOP state shouldn't affect the IDLE->START transition.
# But the test is failing at vec 430 (IDLE->START area).
#
# Wait - I also changed the expected output vectors! I regenerated them using
# the golden model. But the golden model might not match the RTL timing.
# The ORIGINAL vectors (before my regeneration) were correct for the old RTL.
# My regeneration using the golden model produced WRONG vectors because the
# golden model doesn't match the RTL timing.
#
# So the fix is: DON'T regenerate the vectors. The original vectors were
# correct for the old TX behavior. My change to the STOP state only affects
# back-to-back frames, which don't happen in the unit test (frames are 5209 
# cycles apart). So the original vectors should still be correct for the new TX!
#
# I need to restore the original vectors. Let me check if git has them.

import subprocess
result = subprocess.run(['sh','-c','git diff --stat'], capture_output=True, text=True)
print(result.stdout[:2000])