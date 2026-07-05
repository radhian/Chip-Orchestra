module MMIO_Decoder (
    input  wire                    clk,
    input  wire                    rst_n,
    
    // Address bus (8-bit)
    input  wire [7:0]              addr,
    
    // Data bus
    input  wire [7:0]              data_in,
    output reg  [7:0]              data_out,
    
    // Control signals
    input  wire                    write_en,
    output reg                     read_en,
    output reg                     write_ack,
    output reg                     rdy      // Ready signal
);

    // Memory map regions (5-bit address decode)
    // 0x00-0x7F: SRAM (handled externally)
    // 0x80-0x83: UART registers
    // 0x90-0x97: CGRA configuration registers
    // 0xC0-0xFF: Boot ROM (handled externally)
    
    // Internal state
    reg [7:0]                      addr_reg;
    reg [7:0]                      data_reg;
    reg                            write_valid;
    reg                            read_valid;
    
    // FSM for memory operations
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            addr_reg <= 8'd0;
            data_reg <= 8'd0;
            write_valid <= 1'b0;
            read_valid <= 1'b0;
            read_en <= 1'b0;
            write_ack <= 1'b0;
            rdy <= 1'b1;
        end else begin
            case (addr_reg[7:3])  // 5-bit address decode
                5'd0: begin  // SRAM region (0x00-0x7F)
                    if (write_en) begin
                        addr_reg <= addr;
                        data_reg <= data_in;
                        write_valid <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end else begin
                        data_reg <= data_in;
                        read_valid <= 1'b1;
                        read_en <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end
                end
                
                5'd1: begin  // UART region (0x80-0x83)
                    if (write_en) begin
                        addr_reg <= addr;
                        data_reg <= data_in;
                        write_valid <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end else begin
                        data_reg <= data_in;
                        read_valid <= 1'b1;
                        read_en <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end
                end
                
                5'd2: begin  // CGRA config region (0x90-0x97)
                    if (write_en) begin
                        addr_reg <= addr;
                        data_reg <= data_in;
                        write_valid <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end else begin
                        data_reg <= data_in;
                        read_valid <= 1'b1;
                        read_en <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end
                end
                
                5'd3: begin  // Boot ROM region (0xC0-0xFF)
                    if (write_en) begin
                        addr_reg <= addr;
                        data_reg <= data_in;
                        write_valid <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end else begin
                        data_reg <= data_in;
                        read_valid <= 1'b1;
                        read_en <= 1'b1;
                        write_ack <= 1'b0;
                        rdy <= 1'b0;
                    end
                end
                
                default: begin
                    addr_reg <= addr;
                    data_reg <= data_in;
                    write_valid <= 1'b0;
                    read_valid <= 1'b0;
                    read_en <= 1'b0;
                    write_ack <= 1'b0;
                    rdy <= 1'b1;
                end
            endcase
            
            // Complete write operation
            if (write_valid) begin
                write_valid <= 1'b0;
                write_ack <= 1'b1;
                rdy <= 1'b1;
            end
            
            // Complete read operation
            if (read_valid) begin
                read_valid <= 1'b0;
                read_en <= 1'b0;
                rdy <= 1'b1;
            end
        end
    end

    // Output data
    data_out <= data_reg;

endmodule