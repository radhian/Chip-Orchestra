# Let me update the golden model for uart_tx to match the new STOP->START behavior,
# then regenerate the test vectors.
#
# First, update the golden model.

import subprocess

# Read the current golden model
result = subprocess.run(['sh','-c','cat golden/model/uart_tx.py'], capture_output=True, text=True)
print(result.stdout)