import json, os, sys
sys.path.insert(0, 'golden')
from model.params import (IMG_W, IMG_H, OUT_W, OUT_H, CLK_FREQ, BAUD_RATE,
                          ADDR_SRAM_BASE, ADDR_UART_TXDATA, ADDR_UART_RXDATA,
                          ADDR_UART_STATUS, ADDR_UART_CTRL, ADDR_CGRA_CFG_BASE,
                          ADDR_CGRA_OPA, ADDR_CGRA_OPB, ADDR_CGRA_RES,
                          ADDR_START, ADDR_STATUS, SOBEL_GX, SOBEL_GY)
from model.sobel_core import sobel_compute
from model.pe import PE
from model.cgra_3x3 import CGRA3x3, CFG_GX, CFG_GY
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.sram_32b import SRAM32B
from model.mmio_bus import MMIOBus
from model.nano_controller import NanoController
from model.reset_sync import ResetSync
from model.uart_rx import UartRx
from model.uart_tx import UartTx
from model.baud_gen import BaudGen
from model.top import sobel_stream

# Load input
with open('context/chip_input_grid.json') as f:
    grid = json.load(f)
pixels_2d = grid['pixels']
flat = [p for row in pixels_2d for p in row]
out = sobel_stream(flat)
print("input len", len(flat), "output len", len(out))
print("out[0:5]", out[0:5])
print("DIV", CLK_FREQ//BAUD_RATE)
print("SOBEL_GX", SOBEL_GX)
print("SOBEL_GY", SOBEL_GY)
print("CFG_GX", CFG_GX)
print("CFG_GY", CFG_GY)