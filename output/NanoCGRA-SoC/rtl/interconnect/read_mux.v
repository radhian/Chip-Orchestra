`timescale 1ns/1ps

`include "smpb_pkg.vh"

module read_mux
(
    input wire [31:0] sram_rdata,
    input wire [31:0] cgra_rdata,
    input wire [31:0] uart_rdata,
    input wire [31:0] gpio_rdata,
    input wire [31:0] timer_rdata,

    input wire [31:0] default_rdata,

    input wire [`SMPB_NUM_SLAVES-1:0] sel,

    output reg [31:0] cpu_rdata
);

always @(*)
begin

    cpu_rdata = default_rdata;

    if(sel[`SMPB_SRAM])
        cpu_rdata = sram_rdata;

    else if(sel[`SMPB_CGRA])
        cpu_rdata = cgra_rdata;

    else if(sel[`SMPB_UART])
        cpu_rdata = uart_rdata;

    else if(sel[`SMPB_GPIO])
        cpu_rdata = gpio_rdata;

    else if(sel[`SMPB_TIMER])
        cpu_rdata = timer_rdata;

end

endmodule