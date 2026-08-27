import sys
sys.path.insert(0, 'golden')
from model.uart_tx import UartTx
from model.params import CLK_FREQ, BAUD_RATE

DIV = CLK_FREQ // BAUD_RATE
print(f"DIV = {DIV}")

tx = UartTx()
tx.reset()
# idle
tx.step(1, 1, 1, 0)
tx.step(1, 1, 1, 0)
# pulse tx_start with byte
tx.step(1, 1, 1, 0x3C)
bits = []
dones = []
for _ in range(DIV * 10 + 5):
    out, done = tx.step(1, 1, 0, 0)
    bits.append(out)
    dones.append(done)

print(f"sum(dones) = {sum(dones)}")
print(f"bits[0:12] = {bits[0:12]}")
print(f"total bits captured = {len(bits)}")

# The issue: tx_start is sampled only on baud tick.
# After reset, baud_gen.cnt=0. It takes DIV-1 cycles to get first tick.
# The tx_start pulse is 1 cycle. If it doesn't coincide with a tick, it's dropped.
# Let's see when ticks happen
tx2 = UartTx()
tx2.reset()
ticks = []
for i in range(DIV*12):
    t = tx2.bg.step(1, 1)
    if t:
        ticks.append(i)
print(f"Tick cycles (first 12): {ticks[:12]}")
print(f"tx_start was pulsed at cycle 2 (0-indexed, after 2 idle steps)")
print(f"Is cycle 2 a tick? {2 in ticks}")