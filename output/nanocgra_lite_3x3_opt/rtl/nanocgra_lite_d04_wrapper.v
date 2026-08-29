`include "params.vh"

module NanoCGRA_Lite #(
    parameter DW = `DATA_WIDTH,
    parameter AW = `ADDR_WIDTH,
    parameter UART_CLK_PER_BIT = 87
) (
    inout  wire vss,
    output wire clk_PU,
    output wire clk_PD,
    input  wire clk,
    output wire rst_n_PU,
    output wire rst_n_PD,
    input  wire rst_n,
    output wire uart_rx_PU,
    output wire uart_rx_PD,
    input  wire uart_rx,
    output wire uart_tx_CS,
    output wire uart_tx_SL,
    output wire uart_tx_IE,
    output wire uart_tx_OE,
    output wire uart_tx_PU,
    output wire uart_tx_PD,
    output wire uart_tx_OUT,
    output wire uart_tx_PDRV0,
    output wire uart_tx_PDRV1,
    input  wire uart_tx_IN,
    inout  wire vdd
);
    wire uart_tx_core;

    assign clk_PU = 1'b0;
    assign clk_PD = 1'b0;
    assign rst_n_PU = 1'b0;
    assign rst_n_PD = 1'b0;
    assign uart_rx_PU = 1'b0;
    assign uart_rx_PD = 1'b0;

    assign uart_tx_CS = 1'b0;
    assign uart_tx_SL = 1'b0;
    assign uart_tx_IE = 1'b0;
    assign uart_tx_OE = 1'b1;
    assign uart_tx_PU = 1'b0;
    assign uart_tx_PD = 1'b0;
    assign uart_tx_OUT = uart_tx_core;
    assign uart_tx_PDRV0 = 1'b0;
    assign uart_tx_PDRV1 = 1'b0;

    NanoCGRA_Lite_core #(
        .DW(DW),
        .AW(AW),
        .UART_CLK_PER_BIT(UART_CLK_PER_BIT)
    ) u_core (
        .clk(clk),
        .rst_n(rst_n),
        .uart_rx(uart_rx),
        .uart_tx(uart_tx_core)
    );
endmodule
