# Now I need to regenerate the uart_tx test vectors.
# Let me understand the test structure from the testbench:
# - 3 warmup cycles with rst_n=1, tx_start=1, data_in=60
# - Then 20853 vectors
# - tx_start pulses at vecs 5209/5210, 10422/10423, 15635/15636 for frames 2-4
#
# The testbench applies inputs and checks outputs cycle by cycle.
# I need to regenerate the expected outputs using the updated golden model.
#
# Let me read the baud_gen golden model first.

import subprocess
result = subprocess.run(['sh','-c','cat golden/model/baud_gen.py'], capture_output=True, text=True)
print(result.stdout)