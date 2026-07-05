//
// NanoCGRA v1 - FazyRV_Core
// Lightweight CPU Controller for RV32I (Minimal)
// CHUNKSIZE = 8, MIN configuration
// Role: Bootloader, Data Loader, CGRA Orchestrator, UART Driver
//

`timescale 1ns / 1ps

module FazyRV_Core (
    input  wire                    clk,
    input  wire                    rst_n,
    
    // Instruction fetch from ROM/SRAM
    input  wire [7:0]              inst_addr,
    input  wire [7:0]              inst_data,
    output reg                     inst_valid,
    
    // Register file interface
    input  wire [7:0]              reg_write_data,
    input  wire [2:0]              reg_write_idx,
    output reg [7:0]               reg_read_data,
    output reg                     reg_write_en,
    
    // Program counter
    output reg [7:0]              pc,
    output reg                     pc_valid,
    
    // Interrupt (disabled)
    input  wire                    irq,
    
    // Status outputs
    output reg                     cpu_busy,
    output reg                     cpu_idle
);

    // Instruction format (8-bit chunks)
    // [7:6] opcode, [5:0] immediate
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

    // Register file (32 registers, 8-bit each)
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
                    // Extract opcode from upper 2 bits
                    opcode <= inst_buffer[7:6];
                    // Extract immediate from lower 6 bits
                    imm <= inst_buffer[5:0];
                    
                    case (opcode)
                        2'b00: state <= STATE_IDLE;  // NOP
                        2'b01: state <= STATE_EXEC;  // LOAD
                        2'b10: state <= STATE_EXEC;  // STORE
                        2'b11: state <= STATE_EXEC;  // ADD
                        2'b00: state <= STATE_EXEC;  // SUB (same opcode as NOP in 2-bit)
                        2'b01: state <= STATE_EXEC;  // AND
                        2'b10: state <= STATE_EXEC;  // OR
                        2'b11: state <= STATE_EXEC;  // XOR
                        2'b00: state <= STATE_EXEC;  // JMP
                        2'b01: state <= STATE_EXEC;  // BNE
                        2'b10: state <= STATE_EXEC;  // BEQ
                        2'b11: state <= STATE_IDLE;  // HALT
                        default: state <= STATE_IDLE;
                    endcase
                end
                
                STATE_EXEC: begin
                    // Read register (Rs from bits 5:3)
                    if (inst_buffer[5:3] > 0 && inst_buffer[5:3] <= 32) begin
                        reg_read_data <= regfile[inst_buffer[5:3]-1];
                    end else begin
                        reg_read_data <= 8'd0;
                    end
                    
                    // Execute operation based on opcode
                    case (opcode)
                        2'b00: alu_result <= reg_read_data;  // NOP
                        2'b01: alu_result <= reg_read_data + imm;  // ADD
                        2'b10: alu_result <= reg_read_data & imm;  // AND
                        2'b11: alu_result <= reg_read_data | imm;  // OR
                        2'b00: alu_result <= reg_read_data ^ imm;  // XOR
                        2'b01: alu_result <= reg_read_data - imm;  // SUB
                        2'b10: alu_result <= reg_read_data;  // LOAD (load immediate)
                        2'b11: alu_result <= reg_read_data;  // STORE (store to memory)
                        2'b00: alu_result <= pc + 8;  // JMP
                        2'b01: alu_result <= pc + 8;  // BNE
                        2'b10: alu_result <= pc + 8;  // BEQ
                        2'b11: alu_result <= 8'd0;  // HALT
                        default: alu_result <= reg_read_data;
                    endcase
                    
                    state <= STATE_WRITE;
                end
                
                STATE_WRITE: begin
                    // Write result to register
                    if (inst_buffer[5:3] > 0 && inst_buffer[5:3] <= 32) begin
                        reg_write_data <= alu_result;
                        reg_write_idx <= inst_buffer[5:3] - 1;
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

    // Register file write
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_write_en <= 1'b0;
            reg_read_data <= 8'd0;
        end else begin
            if (reg_write_en) begin
                regfile[reg_write_idx] <= reg_write_data;
            end
            if (reg_write_idx > 0 && reg_write_idx <= 32) begin
                reg_read_data <= regfile[reg_write_idx-1];
            end else begin
                reg_read_data <= 8'd0;
            end
            reg_write_en <= 1'b0;
        end
    end

endmodule
