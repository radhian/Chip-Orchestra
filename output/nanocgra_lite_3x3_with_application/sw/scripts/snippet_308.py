# The uart_tx_tb uses golden vectors that were generated with the OLD TX behavior
# (with the 1-baud IDLE gap). The back-to-back frame change shifts the timing.
# 
# The testbench sends 4 frames:
# Frame 1: data=60, tx_start at warmup
# Frame 2: data=255, tx_start at vec 5209/5210
# Frame 3: data=165, tx_start at vec 10422/10423
# Frame 4: data=0, tx_start at vec 15635/15636
#
# With the old TX (11 baud per frame): frame cycle = 11*434 = 4774
# Frame 1: starts at warmup, done at ~4340, IDLE for 434
# Frame 2: tx_start at vec 5209 (5209 cycles after vec 0)
# 
# With the new TX (10 baud per frame when back-to-back): frame cycle = 4340
# But the testbench vectors were generated for 4774-cycle frames.
# The tx_start pulses are at specific vec indices that assume the old timing.
#
# The issue: the testbench sends tx_start at vec 5209/5210 for frame 2.
# With the old TX, frame 1 finishes at ~4340, then IDLE for 434, so frame 2
# starts at ~4774. The tx_start at vec 5209 is after frame 1 is done.
# With the new TX, frame 1 finishes at ~4340. The tx_start at vec 5209 is
# 869 cycles later. TX is in IDLE. It starts frame 2.
# But the expected output vectors assume frame 2 starts at a different time.
#
# The key question: should I update the uart_tx testbench/vectors, or should
# I make the TX change in a way that doesn't affect the unit test?
#
# The regression log says "Keep every module's PORTS unchanged."
# It doesn't say keep the testbench unchanged. But the instruction says
# "The RTL already compiles with iverilog and the testbench PASSES — keep it that way."
#
# The MAIN testbench (nano_cgra_3x3_sobel_accelerator_v4_tb) passes.
# But the uart_tx unit testbench fails.
#
# The issue is that the golden vectors for uart_tx were generated with the
# old TX behavior. I need to regenerate them for the new TX.
#
# But wait - the instruction says "The RTL already compiles with iverilog and 
# the testbench PASSES — keep it that way." This refers to the MAIN testbench.
# The unit testbenches are separate.
#
# Actually, let me re-read the instruction more carefully:
# "The RTL already compiles with iverilog and the testbench PASSES — keep it that way."
# "VERIFY YOURSELF before finishing: run_python ... and CHECK it prints TEST PASSED."
#
# The verification command only runs the MAIN testbench. So the MAIN testbench
# must pass. The unit testbenches should ideally also pass, but the instruction
# only requires the main one.
#
# However, I should try to keep the uart_tx unit test passing too.
# The problem is the golden vectors were generated for the old TX.
# I need to regenerate them.
#
# Let me look at the golden model for uart_tx to understand the expected behavior.

import subprocess
result = subprocess.run(['sh','-c','cat golden/model/uart_tx.py'], capture_output=True, text=True)
print(result.stdout[:3000])