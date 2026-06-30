`timescale 1ns/1ps

`include "smpb_pkg.vh"

module ready_mux
(
    input wire sram_ready,
    input wire cgra_ready,
    input wire uart_ready,
    input wire gpio_ready,
    input wire timer_ready,

    input wire default_ready,

    input wire [`SMPB_NUM_SLAVES-1:0] sel,

    output reg cpu_ready
);

always @(*)
begin

    cpu_ready = default_ready;

    if(sel[`SMPB_SRAM])
        cpu_ready = sram_ready;

    else if(sel[`SMPB_CGRA])
        cpu_ready = cgra_ready;

    else if(sel[`SMPB_UART])
        cpu_ready = uart_ready;

    else if(sel[`SMPB_GPIO])
        cpu_ready = gpio_ready;

    else if(sel[`SMPB_TIMER])
        cpu_ready = timer_ready;

end

endmodule