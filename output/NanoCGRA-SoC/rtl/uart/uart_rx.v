`timescale 1ns/1ps
//////////////////////////////////////////////////////////////////////////////////
// NanoCGRA-SoC
//
// UART Receiver
//
//////////////////////////////////////////////////////////////////////////////////

module uart_rx
#(
    parameter DATA_WIDTH = 8
)
(
    input  wire clk,
    input  wire rst_n,

    input  wire sample_tick,
    input  wire enable,

    input  wire rx,

    output reg [DATA_WIDTH-1:0] rx_data,
    output reg rx_valid,

    output reg framing_error,
    output reg busy
);

////////////////////////////////////////////////////////////

localparam ST_IDLE  = 3'd0;
localparam ST_START = 3'd1;
localparam ST_DATA  = 3'd2;
localparam ST_STOP  = 3'd3;
localparam ST_DONE  = 3'd4;

reg [2:0] state;

reg [3:0] sample_cnt;
reg [2:0] bit_cnt;

reg [DATA_WIDTH-1:0] shift_reg;

////////////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin

        state <= ST_IDLE;

        sample_cnt <= 0;
        bit_cnt <= 0;

        shift_reg <= 0;

        rx_data <= 0;

        rx_valid <= 0;

        framing_error <= 0;

        busy <= 0;

    end

    else
    begin

        rx_valid <= 0;

        if(sample_tick)
        begin

            case(state)

            ////////////////////////////////////////////

            ST_IDLE:

            begin

                busy <= 0;

                if(enable && !rx)
                begin

                    sample_cnt <= 0;

                    busy <= 1;

                    state <= ST_START;

                end

            end

            ////////////////////////////////////////////

            ST_START:

            begin

                sample_cnt <= sample_cnt + 1;

                if(sample_cnt == 4'd7)
                begin

                    if(!rx)
                    begin

                        sample_cnt <= 0;
                        bit_cnt <= 0;

                        state <= ST_DATA;
                    end
                    else
                        state <= ST_IDLE;
                end

            end

            ////////////////////////////////////////////

            ST_DATA:

            begin

                sample_cnt <= sample_cnt + 1;

                if(sample_cnt == 4'd15)
                begin

                    sample_cnt <= 0;

                    shift_reg <=
                    {
                        rx,
                        shift_reg[DATA_WIDTH-1:1]
                    };

                    if(bit_cnt == DATA_WIDTH-1)
                        state <= ST_STOP;

                    bit_cnt <= bit_cnt + 1;

                end

            end

            ////////////////////////////////////////////

            ST_STOP:

            begin

                sample_cnt <= sample_cnt + 1;

                if(sample_cnt == 4'd15)
                begin

                    framing_error <= !rx;

                    rx_data <= shift_reg;

                    state <= ST_DONE;
                end

            end

            ////////////////////////////////////////////

            ST_DONE:

            begin

                rx_valid <= 1;

                busy <= 0;

                state <= ST_IDLE;

            end

            endcase

        end

    end

end

endmodule