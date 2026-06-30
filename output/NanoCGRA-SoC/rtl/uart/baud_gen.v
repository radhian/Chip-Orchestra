`timescale 1ns/1ps
//////////////////////////////////////////////////////////////////////////////////
// NanoCGRA-SoC
//
// Module:
//      baud_gen
//
// Description:
//      UART Baud Rate Generator
//
// Features
//  - Programmable baud divider
//  - TX baud tick
//  - RX 16x oversampling tick
//  - One clock domain
//
//////////////////////////////////////////////////////////////////////////////////

module baud_gen
#(
    parameter CLK_FREQ  = 20_000_000,
    parameter BAUD_RATE = 115200
)
(
    input  wire clk,
    input  wire rst_n,

    input  wire enable,

    // Runtime programmable divider
    input  wire [15:0] baud_div,

    output reg baud_tick,
    output reg sample_tick
);

////////////////////////////////////////////////////////////
// Default divider
////////////////////////////////////////////////////////////

localparam integer DEFAULT_DIV =
    CLK_FREQ / BAUD_RATE;

localparam integer DEFAULT_SAMPLE_DIV =
    CLK_FREQ / (BAUD_RATE * 16);

////////////////////////////////////////////////////////////
// Registers
////////////////////////////////////////////////////////////

reg [15:0] baud_counter;
reg [15:0] sample_counter;

wire [15:0] baud_limit;
wire [15:0] sample_limit;

assign baud_limit =
    (baud_div == 16'd0) ?
    DEFAULT_DIV :
    baud_div;

assign sample_limit =
    baud_limit >> 4;      // divide by 16

////////////////////////////////////////////////////////////
// Baud Tick
////////////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin
        baud_counter <= 16'd0;
        baud_tick <= 1'b0;
    end

    else
    begin

        baud_tick <= 1'b0;

        if(enable)
        begin

            if(baud_counter >= baud_limit-1)
            begin
                baud_counter <= 16'd0;
                baud_tick <= 1'b1;
            end
            else
                baud_counter <= baud_counter + 1'b1;

        end
        else
            baud_counter <= 16'd0;

    end

end

////////////////////////////////////////////////////////////
// Sample Tick (16x)
////////////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin
        sample_counter <= 16'd0;
        sample_tick <= 1'b0;
    end

    else
    begin

        sample_tick <= 1'b0;

        if(enable)
        begin

            if(sample_counter >= sample_limit-1)
            begin
                sample_counter <= 16'd0;
                sample_tick <= 1'b1;
            end
            else
                sample_counter <= sample_counter + 1'b1;

        end
        else
            sample_counter <= 16'd0;

    end

end

endmodule