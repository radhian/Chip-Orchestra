`timescale 1ns/1ps

`include "smpb_pkg.vh"

module addr_decoder
(
    input  wire [31:0] addr,

    output reg [`SMPB_NUM_SLAVES-1:0] sel,

    output wire invalid
);

always @(*)
begin

    sel = {`SMPB_NUM_SLAVES{1'b0}};

    case(addr[31:16])

        `SRAM_BASE:
            sel[`SMPB_SRAM] = 1'b1;

        `CGRA_BASE:
            sel[`SMPB_CGRA] = 1'b1;

        `UART_BASE:
            sel[`SMPB_UART] = 1'b1;

        `GPIO_BASE:
            sel[`SMPB_GPIO] = 1'b1;

        `TIMER_BASE:
            sel[`SMPB_TIMER] = 1'b1;

        default:
            sel = {`SMPB_NUM_SLAVES{1'b0}};

    endcase

end

assign invalid = (sel == {`SMPB_NUM_SLAVES{1'b0}});

endmodule