//
// NanoCGRA v1 - CGRA Controller
// Controls 2×2 PE array with configuration registers
//

`timescale 1ns / 1ps

module cgra_controller (
    input  wire                    clk,
    input  wire                    rst_n,
    input  wire                    start,   // Start CGRA execution
    output reg                     done,     // CGRA completion signal
    output reg                     busy,     // CGRA busy indicator
    
    // Configuration registers (memory-mapped)
    input  wire [7:0]              cfg_addr, // Configuration address
    input  wire [7:0]              cfg_data, // Configuration data
    output reg                    cfg_ack,   // Configuration acknowledge
    
    // PE control signals
    output reg [1:0]              pe_row,    // Active PE row
    output reg [1:0]              pe_col,    // Active PE column
    output reg [2:0]              op_code,   // Operation code for active PE
    output reg [7:0]              reg_data,  // Data for active PE
    output reg [2:0]              neighbor,  // Neighbor direction
    output reg [7:0]              neighbor_data, // Data from neighbor
    
    // Status
    output reg                    ready      // Ready for new config
);

    // Configuration register map
    localparam CFG_OP_CODE    = 0x00;  // Operation code
    localparam CFG_REG_DATA   = 0x01;  // Register data
    localparam CFG_NEIGHBOR   = 0x02;  // Neighbor direction
    localparam CFG_NEIGHBOR_DATA = 0x03; // Neighbor data
    localparam CFG_START      = 0x04;  // Start command
    localparam CFG_DONE       = 0x05;  // Done status

    // Internal state
    reg [2:0]                    state;
    reg [2:0]                    pe_idx;    // Current PE index (0-3)
    reg [7:0]                    cfg_buffer; // Buffer for configuration data
    reg [2:0]                    cfg_reg;    // Current configuration register
    reg [2:0]                    cfg_data_valid; // Data valid flag
    
    localparam STATE_IDLE     = 3'b000;
    localparam STATE_CONFIG   = 3'b001;
    localparam STATE_EXEC     = 3'b010;
    localparam STATE_WAIT     = 3'b011;

    // Configuration register decoder
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cfg_ack <= 1'b0;
            cfg_reg <= CFG_OP_CODE;
            cfg_data_valid <= 1'b0;
        end else begin
            case (cfg_addr[7:3])  // 5-bit address decode
                5'd0: cfg_reg <= CFG_OP_CODE;
                5'd1: cfg_reg <= CFG_REG_DATA;
                5'd2: cfg_reg <= CFG_NEIGHBOR;
                5'd3: cfg_reg <= CFG_NEIGHBOR_DATA;
                5'd4: cfg_reg <= CFG_START;
                5'd5: cfg_reg <= CFG_DONE;
                default: cfg_reg <= CFG_OP_CODE;
            endcase
            
            // Store configuration data
            if (cfg_data_valid && cfg_reg == cfg_addr[7:3]) begin
                cfg_buffer <= cfg_data;
                cfg_data_valid <= 1'b0;
            end
            
            cfg_ack <= cfg_data_valid;
        end
    end

    // PE activation and execution
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            done <= 1'b0;
            busy <= 1'b0;
            pe_row <= 2'b00;
            pe_col <= 2'b00;
            op_code <= 3'b000;
            reg_data <= 8'd0;
            neighbor <= 3'b000;
            neighbor_data <= 8'd0;
            ready <= 1'b1;
        end else begin
            case (state)
                STATE_IDLE: begin
                    if (start) begin
                        state <= STATE_CONFIG;
                        busy <= 1'b1;
                        ready <= 1'b0;
                        pe_idx <= 2'b00;
                    end
                end
                
                STATE_CONFIG: begin
                    // Activate next PE in sequence
                    pe_idx <= pe_idx + 2'b01;
                    
                    // Decode neighbor direction from cfg_buffer
                    case (cfg_buffer[4:2])
                        3'd0: neighbor <= 3'b000; // None
                        3'd1: neighbor <= 3'b001; // North
                        3'd2: neighbor <= 3'b010; // South
                        3'd3: neighbor <= 3'b011; // East
                        3'd4: neighbor <= 3'b100; // West
                        default: neighbor <= 3'b000;
                    endcase
                    
                    // Set operation code
                    op_code <= cfg_buffer[1:0];
                    
                    // Set register data
                    reg_data <= cfg_buffer[7:5];
                    
                    // Set neighbor data
                    neighbor_data <= cfg_buffer[7:0];
                    
                    state <= STATE_EXEC;
                end
                
                STATE_EXEC: begin
                    // Execute operation in active PE
                    state <= STATE_WAIT;
                end
                
                STATE_WAIT: begin
                    // Wait for PE to complete
                    if (pe_idx >= 2'b11) begin
                        state <= STATE_IDLE;
                        done <= 1'b1;
                        busy <= 1'b0;
                        ready <= 1'b1;
                    end
                end
            endcase
        end
    end

    // Output PE control signals
    pe_row <= pe_idx[1];
    pe_col <= pe_idx[0];

endmodule
