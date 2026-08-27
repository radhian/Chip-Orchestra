// nano_cgra_3x3_sobel_accelerator_v4.v — TOP module.
// Nano CGRA 3x3 Sobel filter accelerator with UART I/O.
`include "params.vh"

module nano_cgra_3x3_sobel_accelerator_v4 (
    input  wire clk,
    input  wire rst_async_n,
    input  wire data_i,
    output wire data_o
);

    wire rst_n;
    reset_sync u_reset (.clk(clk), .rst_async_n(rst_async_n), .rst_n(rst_n));

    // UART RX
    wire [7:0] rx_byte;
    wire       rx_valid;
    uart_rx u_uart_rx (.clk(clk), .rst_n(rst_n), .rx_in(data_i),
        .rx_byte(rx_byte), .rx_valid(rx_valid));

    // UART TX
    wire       tx_start;
    wire [7:0] tx_data;
    wire       tx_done;
    uart_tx u_uart_tx (.clk(clk), .rst_n(rst_n), .tx_start(tx_start),
        .data_in(tx_data), .tx_out(data_o), .tx_done(tx_done));

    // Controller
    wire [`DATA_W-1:0] pixel_in;
    wire               pixel_shift;
    wire [5:0]         col_cnt;
    wire [5:0]         row_cnt;
    wire               start_cgra;
    wire [7:0]         status;
    wire [`DATA_W-1:0] sobel_out;
    wire               cgra_done;

    nano_controller u_ctrl (.clk(clk), .rst_n(rst_n), .rx_byte(rx_byte),
        .rx_valid(rx_valid), .tx_done(tx_done), .sobel_out(sobel_out),
        .pixel_in(pixel_in), .pixel_shift(pixel_shift), .col_cnt(col_cnt),
        .row_cnt(row_cnt), .start_cgra(start_cgra), .tx_start(tx_start),
        .tx_data(tx_data), .status(status));

    // Line buffers (column-addressed)
    wire [7:0] lb_rn1_rd;
    wire [7:0] lb_rn2_rd;

    line_buffer u_lb_rn1 (.clk(clk), .rst_n(rst_n), .shift_en(pixel_shift),
        .pixel_in(pixel_in), .wr_col(col_cnt), .rd_col(col_cnt), .rd_data(lb_rn1_rd));

    line_buffer u_lb_rn2 (.clk(clk), .rst_n(rst_n), .shift_en(pixel_shift),
        .pixel_in(lb_rn1_rd), .wr_col(col_cnt), .rd_col(col_cnt), .rd_data(lb_rn2_rd));

    // 3x3 window assembler
    wire [71:0] win;
    wire        window_valid;
    window_3x3 u_window (.clk(clk), .rst_n(rst_n), .shift_en(pixel_shift),
        .pixel_in(pixel_in), .lb0_data(lb_rn2_rd), .lb1_data(lb_rn1_rd),
        .col_cnt(col_cnt), .row_cnt(row_cnt), .win(win), .window_valid(window_valid));

    // CGRA / Sobel core
    cgra_3x3 u_cgra (.clk(clk), .rst_n(rst_n), .win(win), .start(start_cgra),
        .sobel_out(sobel_out), .done(cgra_done));

    // SRAM + MMIO (unused in streaming mode but instantiated for completeness)
    wire [4:0] sram_addr;
    wire       sram_wr_en;
    wire [7:0] sram_wdata;
    wire [7:0] sram_rdata;
    sram_32b u_sram (.clk(clk), .rst_n(rst_n), .addr(sram_addr), .wr_en(sram_wr_en),
        .data_in(sram_wdata), .data_out(sram_rdata));

    mmio_bus u_mmio (.clk(clk), .rst_n(rst_n), .mst_addr(8'd0), .mst_wr(1'b0),
        .mst_rd(1'b0), .mst_wdata(8'd0), .mst_rdata(), .sram_sel(), .uart_sel(),
        .cgra_sel(), .sram_addr(sram_addr), .sram_wr_en(sram_wr_en),
        .sram_wdata(sram_wdata), .sram_rdata(sram_rdata), .uart_rdata(8'd0),
        .cgra_rdata(8'd0));

endmodule