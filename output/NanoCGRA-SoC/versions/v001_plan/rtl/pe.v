//
// NanoCGRA v1 - Processing Element (PE)
// GF180MCU Technology - 8-bit ALU with nearest-neighbor routing
//
// Architecture:
//   - 8-bit register
//   - 8-bit ALU (ADD, SUB, AND, OR, XOR, PASS)
//   - Control FSM (IDLE, CONFIG, EXEC, DONE)
//   - Neighbor ports: North, South, East, West
//

`timescale 1ns / 1ps

module pe (
    input  wire                    clk,
    input  wire                    rst_n,
    
    // Data inputs from neighbors
    input  wire [7:0]              data_n,  // North
    input  wire [7:0]              data_s,  // South
    input  wire [7:0]              data_e,  // East
    input  wire [7:0]              data_w,  // West
    
    // Data output to neighbors
    output reg  [7:0]              data_n_out,
    output reg  [7:0]              data_s_out,
    output reg  [7:0]              data_e_out,
    output reg  [7:0]              data_w_out,
    
    // Control signals
    input  wire                    start,   // Start execution
    input  wire                    done,     // PE done signal
    output reg                    pe_busy,   // PE busy indicator
    
    // Configuration
    input  wire [2:0]              op_code,  // Operation code
    input  wire [7:0]              reg_data, // Register data
    input  wire [2:0]              neighbor, // Active neighbor direction
    input  wire [7:0]              neighbor_data, // Data from active neighbor
    
    // Status
    output reg                    ready      // Ready for new config
);

    // Operation codes
    localparam OP_NOP   = 3'b000;
    localparam OP_ADD   = 3'b001;
    localparam OP_SUB   = 3'b010;
    localparam OP_AND   = 3'b011;
    localparam OP_OR    = 3'b100;
    localparam OP_XOR   = 3'b101;
    localparam OP_PASS  = 3'b110;

    // Internal registers
    reg [7:0]                    local_reg;
    reg [7:0]                    result;
    reg [2:0]                    state;
    
    localparam STATE_IDLE   = 3'b000;
    localparam STATE_CONFIG = 3'b001;
    localparam STATE_EXEC   = 3'b010;
    localparam STATE_DONE   = 3'b011;

    // FSM State Machine
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= STATE_IDLE;
            local_reg <= 8'd0;
            result <= 8'd0;
            pe_busy <= 1'b0;
            ready <= 1'b1;
        end else begin
            case (state)
                STATE_IDLE: begin
                    if (start) begin
                        state <= STATE_CONFIG;
                        pe_busy <= 1'b1;
                        ready <= 1'b0;
                    end
                end
                
                STATE_CONFIG: begin
                    if (neighbor) begin
                        local_reg <= neighbor_data;
                        state <= STATE_EXEC;
                    end
                end
                
                STATE_EXEC: begin
                    case (op_code)
                        OP_NOP:   result <= local_reg;
                        OP_ADD:   result <= local_reg + neighbor_data;
                        OP_SUB:   result <= local_reg - neighbor_data;
                        OP_AND:   result <= local_reg & neighbor_data;
                        OP_OR:    result <= local_reg | neighbor_data;
                        OP_XOR:   result <= local_reg ^ neighbor_data;
                        OP_PASS:  result <= local_reg;
                        default:  result <= local_reg;
                    end
                    state <= STATE_DONE;
                end
                
                STATE_DONE: begin
                    state <= STATE_IDLE;
                    pe_busy <= 1'b0;
                    ready <= 1'b1;
                end
            endcase
        end
    end

    // Neighbor output ports (output current local_reg value)
    data_n_out <= local_reg;
    data_s_out <= local_reg;
    data_e_out <= local_reg;
    data_w_out <= local_reg;

endmodule
