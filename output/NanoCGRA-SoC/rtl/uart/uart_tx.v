`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// NanoCGRA-SoC
//
// UART Transmitter
//
//////////////////////////////////////////////////////////////////////////////////

module uart_tx
#(
    parameter DATA_WIDTH = 8
)
(
    input  wire clk,
    input  wire rst_n,

    input  wire baud_tick,

    input  wire enable,

    input  wire tx_start,

    input  wire [DATA_WIDTH-1:0] tx_data,

    output reg tx,

    output reg busy,

    output reg done
);

////////////////////////////////////////////////////////////
// FSM
////////////////////////////////////////////////////////////

localparam ST_IDLE  = 2'd0;
localparam ST_START = 2'd1;
localparam ST_DATA  = 2'd2;
localparam ST_STOP  = 2'd3;

reg [1:0] state;

////////////////////////////////////////////////////////////
// Registers
////////////////////////////////////////////////////////////

reg [DATA_WIDTH-1:0] shift_reg;

reg [2:0] bit_cnt;

////////////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin

        state <= ST_IDLE;

        tx <= 1'b1;

        busy <= 1'b0;

        done <= 1'b0;

        shift_reg <= 0;

        bit_cnt <= 0;

    end

    else
    begin

        done <= 1'b0;

        case(state)

        ////////////////////////////////////////////////////
        ST_IDLE:
        ////////////////////////////////////////////////////

        begin

            tx <= 1'b1;

            busy <= 1'b0;

            if(enable && tx_start)
            begin

                shift_reg <= tx_data;

                bit_cnt <= 3'd0;

                busy <= 1'b1;

                state <= ST_START;

            end

        end

        ////////////////////////////////////////////////////
        ST_START
        ////////////////////////////////////////////////////

        begin

            if(baud_tick)
            begin

                tx <= 1'b0;

                state <= ST_DATA;

            end

        end

        ////////////////////////////////////////////////////
        ST_DATA
        ////////////////////////////////////////////////////

        begin

            if(baud_tick)
            begin

                tx <= shift_reg[0];

                shift_reg <=
                {
                    1'b0,
                    shift_reg[DATA_WIDTH-1:1]
                };

                if(bit_cnt == DATA_WIDTH-1)
                    state <= ST_STOP;

                bit_cnt <= bit_cnt + 1'b1;

            end

        end

        ////////////////////////////////////////////////////
        ST_STOP
        ////////////////////////////////////////////////////

        begin

            if(baud_tick)
            begin

                tx <= 1'b1;

                busy <= 1'b0;

                done <= 1'b1;

                state <= ST_IDLE;

            end

        end

        endcase

    end

end

endmodule