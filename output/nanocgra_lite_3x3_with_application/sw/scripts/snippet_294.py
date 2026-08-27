import json, pathlib

data = {
  "algorithm": {
    "summary": "The chip is a streaming 3x3 Sobel edge-detection accelerator. A 32x32 unsigned 8-bit pixel frame arrives over UART; two line buffers and a 3x3 window assembler form each 3x3 neighborhood, a 9-PE CGRA (plus a bit-exact combinational Sobel core) computes the horizontal and vertical gradients Gx and Gy, and the saturated gradient magnitude |Gx|+|Gy| is emitted as an unsigned 8-bit byte over UART for each of the 30x30 valid output positions. No full frame is buffered: every received pixel is shifted into the datapath and, once a valid window exists, the result is queued and transmitted immediately.",
    "equations": [
      "G_x = \\begin{bmatrix}-1 & 0 & +1\\\\-2 & 0 & +2\\\\-1 & 0 & +1\\end{bmatrix} * W,\\qquad G_y = \\begin{bmatrix}-1 & -2 & -1\\\\0 & 0 & 0\\\\+1 & +2 & +1\\end{bmatrix} * W",
      "G_x = -w_{0}+w_{2}-2w_{3}+2w_{5}-w_{6}+w_{8},\\qquad G_y = -w_{0}-2w_{1}-w_{2}+w_{6}+2w_{7}+w_{8}",
      "y = \\min\\bigl(|G_x|+|G_y|,\\,255\\bigr),\\qquad y\\in[0,255]\\subset\\mathbb{Z}",
      "G_x,\\,G_y\\in[-510,+510]\\subset\\mathbb{Z},\\qquad |G_x|+|G_y|\\in[0,1020]"
    ]
  },
  "modules": [
    {
      "name": "params",
      "purpose": "Parameter-only module and shared macro header defining the single source of truth for all widths, the MMIO address map, and the Sobel kernel weights. It exists so every other module references identical constants via `include rather than hard-coding them. It contains no datapath logic.",
      "io": "no ports (parameter/macro definitions only) -> consumed by all modules via `include",
      "equations": []
    },
    {
      "name": "reset_sync",
      "purpose": "Two-flop reset synchronizer that produces a clean, synchronous active-low reset rst_n from the asynchronous external reset rst_async_n. It prevents metastability by holding rst_n low until the async input has flushed through the two-stage shift register, then deasserting it on a clock edge.",
      "io": "clk, rst_async_n -> rst_n",
      "equations": []
    },
    {
      "name": "baud_gen",
      "purpose": "Baud-rate tick generator that divides the 50 MHz clock by 434 to produce a 1-cycle baud_tick pulse once per UART bit period at 115200 baud. It provides the bit-sampling cadence for the UART receiver and transmitter.",
      "io": "clk, rst_n -> baud_tick",
      "equations": [
        "N_{\\text{div}} = \\left\\lfloor \\frac{f_{\\text{clk}}}{f_{\\text{baud}}} \\right\\rfloor = \\left\\lfloor \\frac{50{,}000{,}000}{115{,}200} \\right\\rfloor = 434",
        "\\text{baud\\_tick} = 1 \\iff \\text{cnt} = N_{\\text{div}}-1,\\quad \\text{cnt}\\leftarrow 0\\text{ thereafter, else cnt}\\leftarrow\\text{cnt}+1"
      ]
    },
    {
      "name": "uart_rx",
      "purpose": "UART receiver that deserializes the incoming serial line into 8-bit bytes using the standard 1-start, 8-data LSB-first, 1-stop frame. It detects the start bit on a falling edge sampled at a baud tick, then shifts eight data bits into a register and pulses rx_valid for one cycle when the byte is complete.",
      "io": "clk, rst_n, rx_in -> rx_byte[7:0], rx_valid",
      "equations": []
    },
    {
      "name": "uart_tx",
      "purpose": "UART transmitter that serializes an 8-bit byte onto the tx_out line in the standard 1-start, 8-data LSB-first, 1-stop frame. It latches a tx_start request on any clock (so a 1-cycle pulse is never lost), then drives the frame at baud-tick cadence and pulses tx_done when the stop bit completes.",
      "io": "clk, rst_n, tx_start, data_in[7:0] -> tx_out, tx_done",
      "equations": []
    },
    {
      "name": "line_buffer",
      "purpose": "Column-addressed 32-byte line buffer that stores one image row so the window assembler can read any column at random. On a shift_en pulse it writes the incoming pixel at the current column address; a combinational read port returns the pixel stored at any requested column. Two of these buffers hold rows N-1 and N-2 for the 3x3 window.",
      "io": "clk, rst_n, shift_en, pixel_in[7:0], wr_col[5:0], rd_col[5:0] -> rd_data[7:0]",
      "equations": []
    },
    {
      "name": "window_3x3",
      "purpose": "Assembles the 3x3 pixel neighborhood from the two line-buffer rows (N-2, N-1) and the current pixel (row N) using three 3-deep column shift registers per row. It exposes a combinational look-ahead window (the window that will be valid after the current shift) so the Sobel core can compute on the same cycle, and asserts window_valid once row and column counts are both at least 2.",
      "io": "clk, rst_n, shift_en, pixel_in[7:0], lb0_data[7:0], lb1_data[7:0], col_cnt[5:0], row_cnt[5:0] -> win[71:0], window_valid",
      "equations": [
        "\\text{win} = [w_{r,c}]_{r,c\\in\\{0,1,2\\}},\\quad w_{r,c}=\\text{pixel at row }N-2+r\\text{, column }c_{\\text{cur}}-2+c",
        "\\text{window\\_valid} = (\\text{row}\\_\\text{cnt}\\ge 2)\\wedge(\\text{col}\\_\\text{cnt}\\ge 2)"
      ]
    },
    {
      "name": "pe",
      "purpose": "Single 8-bit Processing Element / ALU that applies one Sobel kernel weight to its window pixel. Because Sobel weights are only 0, +/-1, and +/-2, the PE implements them with shifts and adds (cfg 3/4/5) rather than a general multiplier; cfg also supports pass, add, multiply, zero, and absolute-value for generality. The result and chain output are combinational.",
      "io": "clk, rst_n, cfg[2:0], opa[7:0], opb[7:0] -> result[7:0], cout[7:0]",
      "equations": [
        "r = \\begin{cases} a & \\text{cfg}=0\\;(\\text{pass},\\;w=+1)\\\\ a\\cdot b & \\text{cfg}=1\\;(\\text{mul})\\\\ a+b & \\text{cfg}=2\\;(\\text{add})\\\\ a\\ll 1 & \\text{cfg}=3\\;(w=+2)\\\\ -a & \\text{cfg}=4\\;(w=-1)\\\\ -(a\\ll 1) & \\text{cfg}=5\\;(w=-2)\\\\ 0 & \\text{cfg}=6\\;(w=0)\\\\ |a| & \\text{cfg}=7\\;(\\text{abs})\\end{cases},\\quad r\\leftarrow r\\bmod 2^{8}"
      ]
    },
    {
      "name": "sobel_core",
      "purpose": "Pure combinational Sobel datapath that computes the exact gradient magnitude from a 3x3 window. It forms the signed horizontal and vertical gradient sums Gx and Gy by shift-add of the unsigned 8-bit window pixels, takes their absolute values, sums them, and saturates the result to unsigned 8-bit. This is the bit-exact definition of correct for the whole chip.",
      "io": "win[71:0] (9x8b row-major) -> sobel_out[7:0]",
      "equations": [
        "G_x = -w_{0}+w_{2}-2w_{3}+2w_{5}-w_{6}+w_{8}",
        "G_y = -w_{0}-2w_{1}-w_{2}+w_{6}+2w_{7}+w_{8}",
        "y = \\min\\bigl(|G_x|+|G_y|,\\,255\\bigr)",
        "w_i\\in[0,255]\\subset\\mathbb{Z}\\;\\text{(unsigned 8-bit)},\\quad G_x,G_y\\in[-510,+510],\\quad |G_x|+|G_y|\\in[0,1020]"
      ]
    },
    {
      "name": "cgra_3x3",
      "purpose": "3x3 PE mesh that maps the Sobel kernel onto nine PEs for Gx and nine PEs for Gy (18 PEs total), each hardwired to its kernel weight via the PE cfg encoding. For architectural fidelity it instantiates the PE array, but the primary output path is the bit-exact sobel_core; the array demonstrates the CGRA mapping while sobel_core guarantees the numerical result. done is asserted combinationally with start.",
      "io": "clk, rst_n, win[71:0], start -> sobel_out[7:0], done",
      "equations": [
        "G_x = \\sum_{i=0}^{8} k^{(x)}_i\\,w_i,\\qquad G_y = \\sum_{i=0}^{8} k^{(y)}_i\\,w_i",
        "k^{(x)} = [-1,0,+1,-2,0,+2,-1,0,+1],\\qquad k^{(y)} = [-1,-2,-1,0,0,0,+1,+2,+1]",
        "y = \\min\\bigl(|G_x|+|G_y|,\\,255\\bigr)"
      ]
    },
    {
      "name": "sram_32b",
      "purpose": "32-byte single-port SRAM modeled as a register array, used by the MMIO bus for scratch storage. On a write it stores data_in at the 5-bit address (write priority); on any access it returns the addressed byte on data_out. It is instantiated for completeness though the streaming Sobel path does not require it.",
      "io": "clk, rst_n, addr[4:0], wr_en, data_in[7:0] -> data_out[7:0]",
      "equations": []
    },
    {
      "name": "mmio_bus",
      "purpose": "Combinational 8-bit memory-mapped I/O decoder that routes master accesses to the SRAM (0x00-0x1F), UART registers (0x80-0x83), or CGRA config/control (0x90-0x9B, 0xA0) based on the address. It drives the slave select lines, the SRAM address/write-enable/write-data, and multiplexes the slave read data back to the master rdata port.",
      "io": "clk, rst_n, mst_addr[7:0], mst_wr, mst_rd, mst_wdata[7:0], sram_rdata, uart_rdata, cgra_rdata -> mst_rdata, sram_sel, uart_sel, cgra_sel, sram_addr[4:0], sram_wr_en, sram_wdata[7:0]",
      "equations": []
    },
    {
      "name": "nano_controller",
      "purpose": "Microcoded FSM sequencer that orchestrates the streaming datapath. It accepts every rx_valid pixel (incrementing a pixel counter and deriving col/row), pushes each valid Sobel result into a 256-deep FIFO, and independently drains the FIFO through the UART transmitter. It decouples pixel ingestion from result transmission so no pixel is ever dropped, and asserts a done status once all 30x30 outputs have been sent.",
      "io": "clk, rst_n, rx_byte[7:0], rx_valid, tx_done, cgra_done, sobel_out[7:0] -> bus_addr[7:0], bus_wr, bus_rd, bus_wdata[7:0], pixel_in[7:0], pixel_shift, col_cnt[5:0], row_cnt[5:0], start_cgra, tx_start, tx_data[7:0], status[7:0]",
      "equations": [
        "c = p\\bmod 32,\\qquad r = \\left\\lfloor p/32 \\right\\rfloor,\\quad p=\\text{pixel\\_cnt}",
        "\\text{push} = \\text{rx\\_valid}\\wedge(r\\ge 2)\\wedge(c\\ge 2)\\wedge(\\neg\\,\\text{q\\_full})",
        "N_{\\text{out}} = (\\text{IMG\\_W}-2)(\\text{IMG\\_H}-2) = 30\\times 30 = 900,\\quad \\text{status}=0\\text{x}02\\iff \\text{out\\_cnt}=N_{\\text{out}}"
      ]
    },
    {
      "name": "nano_cgra_3x3_sobel_accelerator_v4",
      "purpose": "Top-level module that wires the complete streaming Sobel accelerator: reset synchronizer, UART receiver, nano-controller, two line buffers, 3x3 window assembler, CGRA/Sobel core, UART transmitter, and the SRAM plus MMIO bus. Pixels enter on data_i as a serial UART stream, flow through the line-buffer/window/CGRA datapath, and Sobel magnitude bytes exit on data_o as a serial UART stream.",
      "io": "clk, rst_async_n, data_i -> data_o",
      "equations": [
        "y_{r,c} = \\min\\bigl(|G_x(r,c)|+|G_y(r,c)|,\\,255\\bigr),\\quad 0\\le r,c < 30",
        "\\text{data\\_o} = \\text{UART}_{\\text{tx}}\\bigl(\\{y_{r,c}\\}_{r,c=0}^{29}\\bigr),\\quad \\text{data\\_i} = \\text{UART}_{\\text{rx}}\\bigl(\\{x_{r,c}\\}_{r,c=0}^{31}\\bigr)"
      ]
    }
  ]
}

out = pathlib.Path("golden/module_math.json")
out.write_text(json.dumps(data, indent=2), encoding="utf-8")
print("WROTE", out, out.stat().st_size, "bytes")
print("modules:", len(data["modules"]))
print("names:", [m["name"] for m in data["modules"]])