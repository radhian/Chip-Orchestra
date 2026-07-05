//
// NanoCGRA v1 - FazyRV Minimal CPU (RV32I)
// Lightweight controller for CGRA orchestration
// CHUNKSIZE = 8, MIN configuration
//

`timescale 1ns / 1ps

module fazyrv (
    input  wire                    clk,
    input  wire                    rst_n,
    
    // Instruction fetch
    input  wire [7:0]              inst_addr,
    input  wire [7:0]              inst_data,
    output reg                     inst_valid,
    
    // Register file
    input  wire [7:0]              reg_write_data,
    input  wire [2:0]              reg_write_idx,
    output reg [7:0]               reg_read_data,
    output reg                     reg_write_en,
    
    // Program counter
    output reg [7:0]              pc,
    output reg                     pc_valid,
    
    // Interrupt/exception (disabled)
    input  wire                    irq,
    
    // Status
    output reg                     cpu_busy,
    output reg                     cpu_idle
);

    // Instruction format (8-bit chunks)
    // [7:6] opcode, [5:0] immediate/register
    localparam OP_NOP   = 6'b000000;
    localparam OP_LOAD  = 6'b000001;
    localparam OP_STORE = 6'b000010;
    localparam OP_ADD   = 6'b000011;
    localparam OP_SUB   = 6'b000100;
    localparam OP_AND   = 6'b000101;
    localparam OP_OR    = 6'b000110;
    localparam OP_XOR   = 6'b000111;
    localparam OP_JMP   = 6'b001000;
    localparam OP_BNE   = 6'b001001;
    localparam OP_BEQ   = 6'b001010;
    localparam OP_HALT  = 6'b001011;

    // Register file
    reg [7:0]                    regfile [31:0];
    
    // Internal state
    reg [2:0]                    state;
    reg [7:0]                    inst_buffer;
    reg [2:0]                    opcode;
    reg [2:0]                    rs, rt, rd;
    reg [7:0]                    imm;
    reg [7:0]                    alu_result;
    reg                         inst_ready;
    
    localparam STATE_IDLE     = 3'b000;
    localparam STATE_FETCH    = 3'b001;
    localparam STATE_DECODE   = 3'b010;
    localparam STATE_EXEC     = 3'b011;
    localparam STATE_WRITE    = 3'b100;

    // Instruction fetch
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            inst_valid <= 1'b0;
            inst_buffer <= 8'd0;
            inst_ready <= 1'b0;
        end else begin
            if (irq) begin
                inst_valid <= 1'b0;
                inst_ready <= 1'b0;
            end else begin
                inst_buffer <= inst_data;
                inst_valid <= 1'b1;
                inst_ready <= 1'b1;
            end
        end
    end

    // Decode and execute
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= STATE_IDLE;
            pc <= 8'd0;
            pc_valid <= 1'b0;
            cpu_busy <= 1'b0;
            cpu_idle <= 1'b1;
            reg_write_en <= 1'b0;
            reg_read_data <= 8'd0;
        end else begin
            case (state)
                STATE_IDLE: begin
                    if (inst_ready) begin
                        state <= STATE_FETCH;
                        cpu_busy <= 1'b1;
                        cpu_idle <= 1'b0;
                    end
                end
                
                STATE_FETCH: begin
                    inst_addr <= pc;
                    state <= STATE_DECODE;
                end
                
                STATE_DECODE: begin
                    opcode <= inst_buffer[7:6];
                    rs <= inst_buffer[5:3];
                    rt <= inst_buffer[2:0];
                    imm <= inst_buffer[7:0];
                    
                    case (opcode)
                        OP_NOP:   state <= STATE_IDLE;
                        OP_LOAD:   state <= STATE_EXEC;
                        OP_STORE:  state <= STATE_EXEC;
                        OP_ADD:    state <= STATE_EXEC;
                        OP_SUB:    state <= STATE_EXEC;
                        OP_AND:    state <= STATE_EXEC;
                        OP_OR:     state <= STATE_EXEC;
                        OP_XOR:    state <= STATE_EXEC;
                        OP_JMP:    state <= STATE_EXEC;
                        OP_BNE:    state <= STATE_EXEC;
                        OP_BEQ:    state <= STATE_EXEC;
                        OP_HALT:   state <= STATE_IDLE;
                        default:   state <= STATE_IDLE;
                    endcase
                end
                
                STATE_EXEC: begin
                    // Read registers
                    reg_read_data <= regfile[rs-1];
                    
                    case (opcode)
                        OP_NOP:   alu_result <= reg_read_data;
                        OP_LOAD:   alu_result <= reg_read_data;
                        OP_STORE:  alu_result <= reg_read_data;
                        OP_ADD:    alu_result <= reg_read_data + imm;
                        OP_SUB:    alu_result <= reg_read_data - imm;
                        OP_AND:    alu_result <= reg_read_data & imm;
                        OP_OR:     alu_result <= reg_read_data | imm;
                        OP_XOR:    alu_result <= reg_read_data ^ imm;
                        OP_JMP:    alu_result <= pc;
                        OP_BNE:    alu_result <= pc;
                        OP_BEQ:    alu_result <= pc;
                        OP_HALT:   alu_result <= pc;
                        default:   alu_result <= reg_read_data;
                    endcase
                    
                    state <= STATE_WRITE;
                end
                
                STATE_WRITE: begin
                    if (opcode != OP_NOP && opcode != OP_HALT) begin
                        reg_write_data <= alu_result;
                        reg_write_idx <= rs - 1;
                        reg_write_en <= 1'b1;
                    end
                    state <= STATE_IDLE;
                    cpu_busy <= 1'b0;
                    cpu_idle <= 1'b1;
                end
            endcase
        end
    end

    // Program counter
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pc <= 8'd0;
            pc_valid <= 1'b0;
        end else begin
            if (state == STATE_IDLE) begin
                pc <= 8'd0;
            end else begin
                pc <= pc + 8;  // 8-bit instructions
            end
            pc_valid <= 1'b1;
        end
    end

    // Register file read
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_read_data <= 8'd0;
            reg_write_en <= 1'b0;
        end else begin
            if (reg_write_en) begin
                regfile[reg_write_idx] <= reg_write_data;
            end
            if (reg_write_idx > 0 && reg_write_idx <= 31) begin
                reg_read_data <= regfile[reg_write_idx-1];
            end else begin
                reg_read_data <= 8'd0;
            end
            reg_write_en <= 1'b0;
        end
    end

endmodule
