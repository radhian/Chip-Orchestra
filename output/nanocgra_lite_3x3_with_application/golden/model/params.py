"""Shared parameters mirroring rtl/params.vh.

All arithmetic is integer / fixed-point at the boundaries.
Pixel data is unsigned 8-bit (0..255).
Sobel intermediate sums are signed 9-bit (-510..+510); the final
magnitude |Gx|+|Gy| is saturated to unsigned 8-bit (0..255).
"""

# Clock / UART
CLK_FREQ   = 50_000_000   # 50 MHz
BAUD_RATE  = 115_200      # UART baud
DATA_W     = 8            # pixel / data width (bits)

# Image geometry
IMG_W      = 32           # image width  (pixels)
IMG_H      = 32           # image height (pixels)
OUT_W      = 30           # output width  = IMG_W - 2
OUT_H      = 30           # output height = IMG_H - 2
LINE_BUF_W = IMG_W        # line buffer width = one row

# MMIO address map (8-bit address space)
ADDR_SRAM_BASE     = 0x00  # 0x00-0x1F : SRAM (32 B)
ADDR_UART_TXDATA   = 0x80
ADDR_UART_RXDATA   = 0x81
ADDR_UART_STATUS   = 0x82
ADDR_UART_CTRL     = 0x83
ADDR_CGRA_CFG_BASE = 0x90  # 0x90-0x98 : PE config (9 PEs)
ADDR_CGRA_OPA      = 0x99
ADDR_CGRA_OPB      = 0x9A
ADDR_CGRA_RES      = 0x9B
ADDR_START         = 0xA0
ADDR_STATUS        = 0xA1  # {6'b0, done, busy}

# Sobel kernel weights (Gx, Gy) per PE position (row-major: 0..8)
#   PE0 top-left, PE1 top-mid, PE2 top-right
#   PE3 mid-left, PE4 center,  PE5 mid-right
#   PE6 bot-left, PE7 bot-mid, PE8 bot-right
SOBEL_GX = [-1,  0, +1,
            -2,  0, +2,
            -1,  0, +1]
SOBEL_GY = [-1, -2, -1,
             0,  0,  0,
            +1, +2, +1]

def u8(v):
    """Mask to unsigned 8-bit."""
    return int(v) & 0xFF

def sat_u8(v):
    """Saturate to unsigned 8-bit (0..255)."""
    v = int(v)
    if v < 0:   return 0
    if v > 255: return 255
    return v

def s8(v):
    """Interpret 8-bit as signed two's complement."""
    v = int(v) & 0xFF
    return v - 256 if v & 0x80 else v