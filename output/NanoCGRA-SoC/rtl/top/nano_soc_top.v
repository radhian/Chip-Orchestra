`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
//
//
// NanoCGRA-SoC
//
// Version : v0.1
//
// Current Components
// ------------------
//  - SMPB Interconnect
//  - UART
//
// Future
// ------
//  - FAZYRV CPU
//  - SRAM
//  - CGRA
//  - GPIO
//  - TIMER
//
//////////////////////////////////////////////////////////////////////////////////

module nano_soc_top
(
    ////////////////////////////////////////////////////////////
    // Clock / Reset
    ////////////////////////////////////////////////////////////

    input  wire clk,
    input  wire rst_n,

    ////////////////////////////////////////////////////////////
    // UART Pins
    ////////////////////////////////////////////////////////////

    input  wire uart_rx,
    output wire uart_tx,

    ////////////////////////////////////////////////////////////
    // Interrupt
    ////////////////////////////////////////////////////////////

    output wire uart_irq
);

////////////////////////////////////////////////////////////
//
// CPU BUS (Placeholder)
//
// These signals will eventually come from fazyrv_wrapper.v
//
////////////////////////////////////////////////////////////

wire        cpu_valid;
wire        cpu_write;
wire [31:0] cpu_addr;
wire [31:0] cpu_wdata;
wire [3:0]  cpu_wstrb;

wire [31:0] cpu_rdata;
wire        cpu_ready;
wire        cpu_error;

////////////////////////////////////////////////////////////
//
// Slave Select
//
////////////////////////////////////////////////////////////

wire sram_sel;
wire cgra_sel;
wire uart_sel;
wire gpio_sel;
wire timer_sel;

////////////////////////////////////////////////////////////
//
// SRAM (Stub)
//
////////////////////////////////////////////////////////////

wire [31:0] sram_rdata;
wire        sram_ready;
wire        sram_error;

assign sram_rdata = 32'd0;
assign sram_ready = 1'b1;
assign sram_error = 1'b0;

////////////////////////////////////////////////////////////
//
// CGRA (Stub)
//
////////////////////////////////////////////////////////////

wire [31:0] cgra_rdata;
wire        cgra_ready;
wire        cgra_error;

assign cgra_rdata = 32'd0;
assign cgra_ready = 1'b1;
assign cgra_error = 1'b0;

////////////////////////////////////////////////////////////
//
// GPIO (Stub)
//
////////////////////////////////////////////////////////////

wire [31:0] gpio_rdata;
wire        gpio_ready;
wire        gpio_error;

assign gpio_rdata = 32'd0;
assign gpio_ready = 1'b1;
assign gpio_error = 1'b0;

////////////////////////////////////////////////////////////
//
// TIMER (Stub)
//
////////////////////////////////////////////////////////////

wire [31:0] timer_rdata;
wire        timer_ready;
wire        timer_error;

assign timer_rdata = 32'd0;
assign timer_ready = 1'b1;
assign timer_error = 1'b0;

////////////////////////////////////////////////////////////
//
// UART
//
////////////////////////////////////////////////////////////

wire [31:0] uart_rdata;
wire        uart_ready;
wire        uart_error;

uart_top u_uart
(
    .clk        (clk),
    .rst_n      (rst_n),

    //------------------------------------------------------
    // SMPB Slave Interface
    //------------------------------------------------------

    .sel        (uart_sel),
    .valid      (cpu_valid),
    .write      (cpu_write),
    .addr       (cpu_addr),
    .wdata      (cpu_wdata),
    .wstrb      (cpu_wstrb),

    .rdata      (uart_rdata),
    .ready      (uart_ready),
    .error      (uart_error),

    //------------------------------------------------------
    // UART Pins
    //------------------------------------------------------

    .uart_rx    (uart_rx),
    .uart_tx    (uart_tx),

    //------------------------------------------------------
    // Interrupt
    //------------------------------------------------------

    .irq        (uart_irq)
);

////////////////////////////////////////////////////////////
//
// SMPB Interconnect
//
////////////////////////////////////////////////////////////

smpb_interconnect u_interconnect
(
    //------------------------------------------------------
    // CPU
    //------------------------------------------------------

    .cpu_valid      (cpu_valid),
    .cpu_write      (cpu_write),
    .cpu_addr       (cpu_addr),
    .cpu_wdata      (cpu_wdata),
    .cpu_wstrb      (cpu_wstrb),

    .cpu_rdata      (cpu_rdata),
    .cpu_ready      (cpu_ready),
    .cpu_error      (cpu_error),

    //------------------------------------------------------
    // SRAM
    //------------------------------------------------------

    .sram_sel       (sram_sel),
    .sram_rdata     (sram_rdata),
    .sram_ready     (sram_ready),
    .sram_error     (sram_error),

    //------------------------------------------------------
    // CGRA
    //------------------------------------------------------

    .cgra_sel       (cgra_sel),
    .cgra_rdata     (cgra_rdata),
    .cgra_ready     (cgra_ready),
    .cgra_error     (cgra_error),

    //------------------------------------------------------
    // UART
    //------------------------------------------------------

    .uart_sel       (uart_sel),
    .uart_rdata     (uart_rdata),
    .uart_ready     (uart_ready),
    .uart_error     (uart_error),

    //------------------------------------------------------
    // GPIO
    //------------------------------------------------------

    .gpio_sel       (gpio_sel),
    .gpio_rdata     (gpio_rdata),
    .gpio_ready     (gpio_ready),
    .gpio_error     (gpio_error),

    //------------------------------------------------------
    // TIMER
    //------------------------------------------------------

    .timer_sel      (timer_sel),
    .timer_rdata    (timer_rdata),
    .timer_ready    (timer_ready),
    .timer_error    (timer_error)
);

////////////////////////////////////////////////////////////
//
// Temporary CPU Stub
//
// Remove when fazyrv_wrapper is integrated.
//
////////////////////////////////////////////////////////////

assign cpu_valid = 1'b0;
assign cpu_write = 1'b0;
assign cpu_addr  = 32'd0;
assign cpu_wdata = 32'd0;
assign cpu_wstrb = 4'b0000;

endmodule