//============================================================================
// nanocgra_lite.v  -  NanoCGRA-Lite top level (SoC integration).
//   * 8-bit MMIO bus (single 8-bit address + 8-bit data, we/re strobes)
//   * 128B single-port SRAM (arbitrated between host bus and controller)
//   * 2x2 CGRA (4 PEs)
//   * FSM-only Nano Controller
//   * Memory-mapped UART (TX/RX, no FIFO/DMA/IRQ)
//   Single clock domain, synchronous reset. Synthesizable, no latches.
//
//   Memory map:
//     0x00-0x7F  SRAM (128B)
//     0x80-0x83  UART (TXDATA/RXDATA/STATUS/CTRL)
//     0x90-0x97  CGRA config (cfg0..3, opa_addr, opb_addr, res_addr, rsvd)
//     0xA0       START (write triggers a CGRA run)
//     0xA1       STATUS (read: {6'b0, done, busy})
//============================================================================
`include "params.vh"

module NanoCGRA_Lite #(
    parameter DW = `DATA_WIDTH,
    parameter AW = `ADDR_WIDTH,
    parameter UART_CLK_PER_BIT = 87
) (
    input  wire            clk,
    input  wire            rst_n,

    // 8-bit MMIO host bus
    input  wire [AW-1:0]   bus_addr,
    input  wire            bus_we,
    input  wire            bus_re,
    input  wire [DW-1:0]   bus_wdata,
    output wire [DW-1:0]   bus_rdata,

    // UART serial pins
    input  wire            uart_rx,
    output wire            uart_tx,

    // status observability
    output wire            busy,
    output wire [DW-1:0]   cgra_status
);
    // ---------------- Bus decode --------------------------------------
    wire sel_sram, sel_uart, sel_cgra, sel_start, sel_status;
    wire [DW-1:0] sram_dout, uart_rdata;
    wire [DW-1:0] status_rdata;

    bus_decoder #(.DW(DW), .AW(AW)) u_dec (
        .addr(bus_addr),
        .sel_sram(sel_sram), .sel_uart(sel_uart), .sel_cgra(sel_cgra),
        .sel_start(sel_start), .sel_status(sel_status),
        .sram_rdata(sram_dout), .uart_rdata(uart_rdata),
        .status_rdata(status_rdata),
        .rdata(bus_rdata));

    // ---------------- CGRA config registers (0x90-0x97) ---------------
    reg [DW-1:0] cfg0, cfg1, cfg2, cfg3;
    reg [DW-1:0] opa_reg, opb_reg, res_reg;

    always @(posedge clk) begin
        if (!rst_n) begin
            cfg0 <= {DW{1'b0}}; cfg1 <= {DW{1'b0}};
            cfg2 <= {DW{1'b0}}; cfg3 <= {DW{1'b0}};
            opa_reg <= {DW{1'b0}}; opb_reg <= 8'h01; res_reg <= 8'h10;
        end else if (sel_cgra && bus_we) begin
            case (bus_addr[2:0])
                3'd0: cfg0    <= bus_wdata;
                3'd1: cfg1    <= bus_wdata;
                3'd2: cfg2    <= bus_wdata;
                3'd3: cfg3    <= bus_wdata;
                3'd4: opa_reg <= bus_wdata;
                3'd5: opb_reg <= bus_wdata;
                3'd6: res_reg <= bus_wdata;
                default: ; // 0x97 reserved
            endcase
        end
    end

    // ---------------- START strobe ------------------------------------
    wire start_pulse = sel_start && bus_we;

    // ---------------- Nano Controller ---------------------------------
    wire        c_load_cfg, c_load_data, c_en;
    wire [DW-1:0] c_data_a, c_data_b;
    wire        m_sram_we;
    wire [`SRAM_AW-1:0] m_sram_addr;
    wire [DW-1:0] m_sram_din;
    wire        c_busy, c_done;
    wire [DW-1:0] cgra_result;

    nano_controller #(.DW(DW), .AW(`SRAM_AW)) u_ctrl (
        .clk(clk), .rst_n(rst_n),
        .start_pulse(start_pulse),
        .opa_addr(opa_reg[`SRAM_AW-1:0]),
        .opb_addr(opb_reg[`SRAM_AW-1:0]),
        .res_addr(res_reg[`SRAM_AW-1:0]),
        .sram_rdata(sram_dout),
        .cgra_result(cgra_result),
        .cgra_load_cfg(c_load_cfg),
        .cgra_load_data(c_load_data),
        .cgra_en(c_en),
        .data_a(c_data_a), .data_b(c_data_b),
        .m_sram_we(m_sram_we), .m_sram_addr(m_sram_addr), .m_sram_din(m_sram_din),
        .busy(c_busy), .done(c_done));

    assign busy         = c_busy;
    assign status_rdata = {{(DW-2){1'b0}}, c_done, c_busy};
    assign cgra_status  = status_rdata;

    // ---------------- SRAM port arbitration ---------------------------
    // Controller owns the SRAM port while busy; otherwise the host bus does.
    wire [`SRAM_AW-1:0] sram_addr = c_busy ? m_sram_addr : bus_addr[`SRAM_AW-1:0];
    wire                sram_we   = c_busy ? m_sram_we   : (sel_sram && bus_we);
    wire [DW-1:0]       sram_din  = c_busy ? m_sram_din  : bus_wdata;

    sram #(.DW(DW), .AW(`SRAM_AW), .DEPTH(`SRAM_SIZE)) u_sram (
        .clk(clk), .rst_n(rst_n),
        .addr(sram_addr), .we(sram_we), .din(sram_din), .dout(sram_dout));

    // ---------------- UART --------------------------------------------
    uart #(.DW(DW), .CLK_PER_BIT(UART_CLK_PER_BIT)) u_uart (
        .clk(clk), .rst_n(rst_n),
        .we(sel_uart && bus_we), .re(sel_uart && bus_re),
        .reg_sel(bus_addr[1:0]), .wdata(bus_wdata), .rdata(uart_rdata),
        .uart_rx(uart_rx), .uart_tx(uart_tx));

    // ---------------- CGRA --------------------------------------------
    cgra #(.DW(DW)) u_cgra (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(c_load_cfg), .load_data(c_load_data), .en(c_en),
        .cfg0(cfg0), .cfg1(cfg1), .cfg2(cfg2), .cfg3(cfg3),
        .data_a(c_data_a), .data_b(c_data_b),
        .result(cgra_result));
endmodule
