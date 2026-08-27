import sys
sys.path.insert(0, 'golden')
from model.params import *

# Compute expected outputs for params module
# The params module is parameter-only (no ports, no logic).
# We verify the parameter values match between RTL and golden model.
# Stimulus: instantiate params and check its localparams.

print("=== params expected values ===")
print(f"CLK_FREQ = {CLK_FREQ}")
print(f"BAUD_RATE = {BAUD_RATE}")
print(f"DATA_W = {DATA_W}")
print(f"IMG_W = {IMG_W}")
print(f"IMG_H = {IMG_H}")
print(f"OUT_W = {OUT_W}")
print(f"OUT_H = {OUT_H}")
print(f"LINE_BUF_W = {LINE_BUF_W}")
print(f"ADDR_SRAM_BASE = {ADDR_SRAM_BASE}")
print(f"ADDR_UART_TXDATA = {ADDR_UART_TXDATA}")
print(f"ADDR_UART_RXDATA = {ADDR_UART_RXDATA}")
print(f"ADDR_UART_STATUS = {ADDR_UART_STATUS}")
print(f"ADDR_UART_CTRL = {ADDR_UART_CTRL}")
print(f"ADDR_CGRA_CFG_BASE = {ADDR_CGRA_CFG_BASE}")
print(f"ADDR_CGRA_OPA = {ADDR_CGRA_OPA}")
print(f"ADDR_CGRA_OPB = {ADDR_CGRA_OPB}")
print(f"ADDR_CGRA_RES = {ADDR_CGRA_RES}")
print(f"ADDR_START = {ADDR_START}")
print(f"ADDR_STATUS = {ADDR_STATUS}")
print(f"SOBEL_GX = {SOBEL_GX}")
print(f"SOBEL_GY = {SOBEL_GY}")
print(f"SOBEL_SUM_W = 9")
print(f"CGRA_ROWS = 3")
print(f"CGRA_COLS = 3")
print(f"CGRA_NPE = 9")
print(f"SRAM_DEPTH = 32")

# Also compute sobel for a test window to verify the params are used correctly
from model.sobel_core import sobel_compute
test_windows = [
    [100, 100, 100, 100, 100, 100, 100, 100, 100],
    [0, 0, 255, 0, 0, 255, 0, 0, 255],
    [5, 10, 15, 10, 15, 20, 15, 20, 25],
]
for w in test_windows:
    gx, gy, out = sobel_compute(w)
    print(f"sobel_compute({w}) = gx={gx}, gy={gy}, out={out}")