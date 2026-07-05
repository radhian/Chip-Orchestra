module nanocgra_top (
    input  wire                    clk,
    input  wire                    rst_n,
    
    // UART interface
    input  wire                    uart_tx,
    output reg                     uart_rx,
    input  wire                    uart_rx_valid,
    
    // System status
    output reg                     system_ready,
    output reg                     system_busy,
    output reg                     cgra_done,
    output reg                     uart_tx_ready,
    output reg                     uart_rx_ready,
    output reg                     uart_tx_busy,
    output reg                     uart_rx_busy
);

    // Parameters
    localparam DATA_WIDTH = 8;
    localparam ADDR_WIDTH = 8;
    localparam PE_ROWS = 2;
    localparam PE_COLS = 2;
    localparam SRAM_SIZE = 128;

    // Internal wires
    wire [7:0]                    sram_addr;
    wire [7:0]                    sram_data_in;
    wire                          sram_write_en;
    wire                          sram_read_en;
    wire [7:0]                    sram_data_out;
    wire                          sram_rdy;
    
    wire [7:0]                    rom_addr;
    wire [7:0]                    rom_data_out;
    wire                          rom_rdy;
    
    wire [7:0]                    uart_tx_data;
    wire                          uart_tx_en;
    wire [7:0]                    uart_rx_data;
    wire                          uart_rx_en;
    wire                          uart_tx_ready;
    wire                          uart_rx_ready;
    wire                          uart_tx_busy;
    wire                          uart_rx_busy;
    wire                          uart_status;
    wire                          uart_ctrl;
    
    wire [7:0]                    cfg_addr;
    wire [7:0]                    cfg_data;
    wire                          cfg_ack;
    wire [1:0]                   pe_row;
    wire [1:0]                   pe_col;
    wire [2:0]                   op_code;
    wire [7:0]                   reg_data;
    wire [2:0]                   neighbor;
    wire [7:0]                   neighbor_data;
    wire                          cgra_ready;
    
    wire [7:0]                    inst_addr;
    wire [7:0]                    inst_data;
    wire                          inst_valid;
    wire [7:0]                   reg_write_data;
    wire [2:0]                   reg_write_idx;
    wire [7:0]                   reg_read_data;
    wire                          reg_write_en;
    wire [7:0]                   pc;
    wire                          pc_valid;
    wire                          cpu_busy;
    wire                          cpu_idle;
    
    wire [7:0]                    bus_data_in;
    wire                          bus_read_en;
    wire                          bus_write_ack;
    wire                          bus_rdy;

    // Instantiate SRAM
    sram u_sram (
        .clk           (clk),
        .rst_n         (rst_n),
        .addr          (sram_addr),
        .data_in       (sram_data_in),
        .data_out      (sram_data_out),
        .write_en      (sram_write_en),
        .read_en       (sram_read_en),
        .rdy           (sram_rdy)
    );

    // Instantiate Boot ROM
    rom u_rom (
        .clk           (clk),
        .rst_n         (rst_n),
        .addr          (rom_addr),
        .data_out      (rom_data_out),
        .rdy           (rom_rdy)
    );

    // Instantiate UART
    uart u_uart (
        .clk           (clk),
        .rst_n         (rst_n),
        .tx_en         (uart_tx_en),
        .tx_data       (uart_tx_data),
        .rx_en         (uart_rx_en),
        .rx_data       (uart_rx_data),
        .tx_ready      (uart_tx_ready),
        .rx_ready      (uart_rx_ready),
        .tx_busy       (uart_tx_busy),
        .rx_busy       (uart_rx_busy),
        .status        (uart_status),
        .ctrl          (uart_ctrl)
    );

    // Instantiate CGRA Controller
    cgra_controller u_cgra_ctrl (
        .clk           (clk),
        .rst_n         (rst_n),
        .start         (cgra_ready),
        .done          (cgra_done),
        .busy          (system_busy),
        .cfg_addr      (cfg_addr),
        .cfg_data      (cfg_data),
        .cfg_ack       (cfg_ack),
        .pe_row        (pe_row),
        .pe_col        (pe_col),
        .op_code       (op_code),
        .reg_data      (reg_data),
        .neighbor      (neighbor),
        .neighbor_data (neighbor_data),
        .ready         (cgra_ready)
    );

    // Instantiate FazyRV Core
    fazyrv u_fazyrv (
        .clk           (clk),
        .rst_n         (rst_n),
        .inst_addr     (inst_addr),
        .inst_data     (inst_data),
        .inst_valid    (inst_valid),
        .reg_write_data (reg_write_data),
        .reg_write_idx (reg_write_idx),
        .reg_read_data (reg_read_data),
        .reg_write_en  (reg_write_en),
        .pc            (pc),
        .pc_valid      (pc_valid),
        .irq           (1'b0),
        .cpu_busy      (cpu_busy),
        .cpu_idle      (cpu_idle)
    );

    // Instantiate MMIO Bus Decoder
    mmio_bus u_mmio_bus (
        .clk           (clk),
        .rst_n         (rst_n),
        .addr          (cfg_addr),
        .data_in       (cfg_data),
        .data_out      (cfg_data),
        .write_en      (cfg_ack),
        .read_en       (cfg_ack),
        .write_ack     (cfg_ack),
        .rdy           (cgra_ready)
    );

    // System status
    assign system_ready = cgra_ready && rom_rdy && sram_rdy && uart_tx_ready && uart_rx_ready;
    assign system_busy = system_ready && (cpu_busy || cgra_done);

    // UART interface
    assign uart_tx_data = uart_tx ? 8'h41 : 8'h00;
    assign uart_tx_en = uart_tx;
    assign uart_rx_data = uart_rx_valid ? uart_rx : 8'h00;
    assign uart_rx_en = uart_rx_valid;
    assign uart_rx = uart_rx_ready ? uart_rx_data : 8'h00;

    // Address decoding
    assign rom_addr = 8'd0;
    assign sram_addr = cfg_addr[7:3];
    assign cfg_addr = pc[7:3];

    // Control signals
    assign cfg_data = rom_data_out;
    assign cfg_addr = pc[7:3];

endmodule