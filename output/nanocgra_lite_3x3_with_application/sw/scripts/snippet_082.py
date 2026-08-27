import json, os, sys, random
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
import inspect

print("MMIOBus.step sig:", inspect.signature(MMIOBus.step))
print("NanoController.step sig:", inspect.signature(NanoController.step))
print("UartTx.step sig:", inspect.signature(UartTx.step))
print("UartRx.step sig:", inspect.signature(UartRx.step))
print("Window3x3.step sig:", inspect.signature(Window3x3.step))
print("CGRA3x3.step sig:", inspect.signature(CGRA3x3.step))
print("LineBuffer.step sig:", inspect.signature(LineBuffer.step))
print("SRAM32B.step sig:", inspect.signature(SRAM32B.step))
print("PE.step sig:", inspect.signature(PE.step))
print("BaudGen.step sig:", inspect.signature(BaudGen.step))
print("ResetSync.step sig:", inspect.signature(ResetSync.step))