//
// NanoCGRA v1 - SRAM Interface (128 bytes)
// Memory-mapped interface for data storage
//

`timescale 1ns / 1ps

module sram (
    input  wire                    clk,
    input  wire                    rst_n,
    
    // Address bus
    input  wire [7:0]              addr,
    
    // Data bus
    input  wire [7:0]              data_in,
    output reg  [7:0]              data_out,
    
    // Control signals
    input  wire                    write_en,
    input  wire                    read_en,
    output reg                    rdy      // Ready signal
);

    // SRAM array (128 bytes)
    reg [7:0]                    mem [0:127];
    
    // Internal state
    reg [7:0]                    addr_reg;
    reg [7:0]                    data_reg;
    reg                         write_valid;
    reg                         read_valid;
    
    localparam STATE_IDLE      = 3'b000;
    localparam STATE_WRITE     = 3'b001;
    localparam STATE_READ      = 3'b010;

    // FSM for memory operations
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= STATE_IDLE;
            addr_reg <= 8'd0;
            data_reg <= 8'd0;
            write_valid <= 1'b0;
            read_valid <= 1'b0;
            rdy <= 1'b1;
        end else begin
            case (state)
                STATE_IDLE: begin
                    if (write_en) begin
                        state <= STATE_WRITE;
                        write_valid <= 1'b1;
                        rdy <= 1'b0;
                    end else if (read_en) begin
                        state <= STATE_READ;
                        read_valid <= 1'b1;
                        rdy <= 1'b0;
                    end
                end
                
                STATE_WRITE: begin
                    mem[addr_reg] <= data_reg;
                    write_valid <= 1'b0;
                    state <= STATE_IDLE;
                    rdy <= 1'b1;
                end
                
                STATE_READ: begin
                    data_reg <= mem[addr_reg];
                    read_valid <= 1'b0;
                    state <= STATE_IDLE;
                    rdy <= 1'b1;
                end
            endcase
        end
    end

    // Output data
    data_out <= mem[addr_reg];

endmodule
