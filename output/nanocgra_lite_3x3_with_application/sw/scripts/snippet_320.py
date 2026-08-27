# Now compare the RTL-generated vectors with the golden-model-generated vectors
with open('tb/vecs/uart_tx_exp_out.mem') as f:
    golden_out = [line.strip() for line in f if line.strip()]
with open('tb/vecs/uart_tx_exp_out_new.mem') as f:
    rtl_out = [line.strip() for line in f if line.strip()]
with open('tb/vecs/uart_tx_exp_done.mem') as f:
    golden_done = [line.strip() for line in f if line.strip()]
with open('tb/vecs/uart_tx_exp_done_new.mem') as f:
    rtl_done = [line.strip() for line in f if line.strip()]

print(f"Golden out count: {len(golden_out)}, RTL out count: {len(rtl_out)}")
print(f"Golden done count: {len(golden_done)}, RTL done count: {len(rtl_done)}")

diffs = 0
first_diffs = []
for i in range(min(len(golden_out), len(rtl_out))):
    if golden_out[i] != rtl_out[i] or golden_done[i] != rtl_done[i]:
        diffs += 1
        if len(first_diffs) < 10:
            first_diffs.append((i, golden_out[i], rtl_out[i], golden_done[i], rtl_done[i]))

print(f"Total diffs: {diffs}")
for d in first_diffs:
    print(f"  vec {d[0]}: golden(out={d[1]},done={d[3]}) rtl(out={d[2]},done={d[4]})")