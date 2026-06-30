`timescale 1ns/1ps

`include "smpb_pkg.vh"

module smpb_interconnect
(
    //----------------------------------------------------
    // CPU Interface
    //----------------------------------------------------

    input  wire        cpu_valid,
    input  wire        cpu_write,
    input  wire [31:0] cpu_addr,
    input  wire [31:0] cpu_wdata,
    input  wire [3:0]  cpu_wstrb,

    output wire [31:0] cpu_rdata,
    output wire        cpu_ready,
    output wire        cpu_error,

    //----------------------------------------------------
    // SRAM
    //----------------------------------------------------

    output wire        sram_sel,
    input  wire [31:0] sram_rdata,
    input  wire        sram_ready,
    input  wire        sram_error,

    //----------------------------------------------------
    // CGRA
    //----------------------------------------------------

    output wire        cgra_sel,
    input  wire [31:0] cgra_rdata,
    input  wire        cgra_ready,
    input  wire        cgra_error,

    //----------------------------------------------------
    // UART
    //----------------------------------------------------

    output wire        uart_sel,
    input  wire [31:0] uart_rdata,
    input  wire        uart_ready,
    input  wire        uart_error,

    //----------------------------------------------------
    // GPIO
    //----------------------------------------------------

    output wire        gpio_sel,
    input  wire [31:0] gpio_rdata,
    input  wire        gpio_ready,
    input  wire        gpio_error,

    //----------------------------------------------------
    // TIMER
    //----------------------------------------------------

    output wire        timer_sel,
    input  wire [31:0] timer_rdata,
    input  wire        timer_ready,
    input  wire        timer_error
);

wire [`SMPB_NUM_SLAVES-1:0] sel;
wire invalid;

wire [31:0] default_rdata;
wire default_ready;
wire default_error;

////////////////////////////////////////////////////////////
// Address Decode
////////////////////////////////////////////////////////////

addr_decoder u_addr_decoder
(
    .addr(cpu_addr),
    .sel(sel),
    .invalid(invalid)
);

assign sram_sel  = cpu_valid & sel[`SMPB_SRAM];
assign cgra_sel  = cpu_valid & sel[`SMPB_CGRA];
assign uart_sel  = cpu_valid & sel[`SMPB_UART];
assign gpio_sel  = cpu_valid & sel[`SMPB_GPIO];
assign timer_sel = cpu_valid & sel[`SMPB_TIMER];

////////////////////////////////////////////////////////////
// Default Slave
////////////////////////////////////////////////////////////

default_slave u_default_slave
(
    .rdata(default_rdata),
    .ready(default_ready),
    .error(default_error)
);

////////////////////////////////////////////////////////////
// Read Mux
////////////////////////////////////////////////////////////

read_mux u_read_mux
(
    .sram_rdata(sram_rdata),
    .cgra_rdata(cgra_rdata),
    .uart_rdata(uart_rdata),
    .gpio_rdata(gpio_rdata),
    .timer_rdata(timer_rdata),

    .default_rdata(default_rdata),

    .sel(sel),

    .cpu_rdata(cpu_rdata)
);

////////////////////////////////////////////////////////////
// Ready Mux
////////////////////////////////////////////////////////////

ready_mux u_ready_mux
(
    .sram_ready(sram_ready),
    .cgra_ready(cgra_ready),
    .uart_ready(uart_ready),
    .gpio_ready(gpio_ready),
    .timer_ready(timer_ready),

    .default_ready(default_ready),

    .sel(sel),

    .cpu_ready(cpu_ready)
);

////////////////////////////////////////////////////////////
// Error Mux
////////////////////////////////////////////////////////////

error_mux u_error_mux
(
    .sram_error(sram_error),
    .cgra_error(cgra_error),
    .uart_error(uart_error),
    .gpio_error(gpio_error),
    .timer_error(timer_error),

    .default_error(default_error),

    .sel(sel),

    .cpu_error(cpu_error)
);

endmodule