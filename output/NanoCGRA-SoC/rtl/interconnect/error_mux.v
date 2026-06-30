`timescale 1ns/1ps

`include "smpb_pkg.vh"

module error_mux
(
    input wire sram_error,
    input wire cgra_error,
    input wire uart_error,
    input wire gpio_error,
    input wire timer_error,

    input wire default_error,

    input wire [`SMPB_NUM_SLAVES-1:0] sel,

    output reg cpu_error
);

always @(*)
begin

    cpu_error = default_error;

    if(sel[`SMPB_SRAM])
        cpu_error = sram_error;

    else if(sel[`SMPB_CGRA])
        cpu_error = cgra_error;

    else if(sel[`SMPB_UART])
        cpu_error = uart_error;

    else if(sel[`SMPB_GPIO])
        cpu_error = gpio_error;

    else if(sel[`SMPB_TIMER])
        cpu_error = timer_error;

end

endmodule