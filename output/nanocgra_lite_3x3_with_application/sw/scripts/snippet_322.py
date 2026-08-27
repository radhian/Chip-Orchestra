import os
# Clean up temp files
for f in ['tb/vecs/uart_tx_exp_out_new.mem', 'tb/vecs/uart_tx_exp_done_new.mem']:
    if os.path.exists(f):
        os.remove(f)
print("Temp files cleaned up")