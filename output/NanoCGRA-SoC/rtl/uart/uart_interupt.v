`timescale 1ns/1ps
//////////////////////////////////////////////////////////////////////////////////
// UART Interrupt Controller
//////////////////////////////////////////////////////////////////////////////////

module uart_interrupt
(
    input  wire clk,
    input  wire rst_n,

    input  wire tx_empty,
    input  wire rx_ready,
    input  wire overflow,
    input  wire framing_error,

    input  wire [3:0] irq_enable,

    output reg  [3:0] irq_status,
    output wire irq
);

always @(posedge clk or negedge rst_n)
begin
    if(!rst_n)
    begin
        irq_status <= 4'b0000;
    end
    else
    begin
        if(tx_empty)
            irq_status[0] <= 1'b1;

        if(rx_ready)
            irq_status[1] <= 1'b1;

        if(overflow)
            irq_status[2] <= 1'b1;

        if(framing_error)
            irq_status[3] <= 1'b1;
    end
end

assign irq = |(irq_status & irq_enable);

endmodule