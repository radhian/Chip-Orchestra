module Boot_ROM (
    input  wire                    clk,
    input  wire                    rst_n,
    
    // Address bus
    input  wire [7:0]              addr,
    
    // Data output
    output reg  [7:0]              data_out,
    
    // Status
    output reg                     rdy      // Ready signal
);

    // Boot ROM contents (64 bytes)
    // Offset 0x00-0x0F: Reset handler and initialization
    // Offset 0x10-0x1F: Demo program (vector addition)
    // Offset 0x20-0x3F: UART output routine
    // Offset 0x40-0x5F: Idle loop
    // Offset 0x60-0x7F: Reserved
    
    reg [7:0]                    mem [0:63];
    
    // Initialize ROM with boot code
    initial begin
        // Reset handler (0x00-0x0F)
        mem[0]   = 8'h00;  // NOP
        mem[1]   = 8'h01;  // Initialize UART
        mem[2]   = 8'h02;  // Initialize CGRA
        mem[3]   = 8'h03;  // Load data to SRAM
        mem[4]   = 8'h04;  // Configure CGRA
        mem[5]   = 8'h05;  // Start CGRA
        mem[6]   = 8'h06;  // Wait for done
        mem[7]   = 8'h07;  // Read results
        mem[8]   = 8'h08;  // Transmit via UART
        mem[9]   = 8'h09;  // NOP
        mem[10]  = 8'h0A;  // NOP
        mem[11]  = 8'h0B;  // NOP
        mem[12]  = 8'h0C;  // NOP
        mem[13]  = 8'h0D;  // NOP
        mem[14]  = 8'h0E;  // NOP
        mem[15]  = 8'h0F;  // NOP
        
        // Demo program - vector addition (0x10-0x1F)
        mem[16]  = 8'h10;  // Load vector A to SRAM
        mem[17]  = 8'h11;  // Load vector B to SRAM
        mem[18]  = 8'h12;  // Configure CGRA for ADD
        mem[19]  = 8'h13;  // Start CGRA
        mem[20]  = 8'h14;  // Wait for done
        mem[21]  = 8'h15;  // Read results
        mem[22]  = 8'h16;  // Transmit via UART
        mem[23]  = 8'h17;  // NOP
        mem[24]  = 8'h18;  // NOP
        mem[25]  = 8'h19;  // NOP
        mem[26]  = 8'h1A;  // NOP
        mem[27]  = 8'h1B;  // NOP
        mem[28]  = 8'h1C;  // NOP
        mem[29]  = 8'h1D;  // NOP
        mem[30]  = 8'h1E;  // NOP
        mem[31]  = 8'h1F;  // NOP
        
        // UART output routine (0x20-0x3F)
        mem[32]  = 8'h20;  // Initialize UART
        mem[33]  = 8'h21;  // Send byte
        mem[34]  = 8'h22;  // Wait for TX complete
        mem[35]  = 8'h23;  // NOP
        mem[36]  = 8'h24;  // NOP
        mem[37]  = 8'h25;  // NOP
        mem[38]  = 8'h26;  // NOP
        mem[39]  = 8'h27;  // NOP
        mem[40]  = 8'h28;  // NOP
        mem[41]  = 8'h29;  // NOP
        mem[42]  = 8'h2A;  // NOP
        mem[43]  = 8'h2B;  // NOP
        mem[44]  = 8'h2C;  // NOP
        mem[45]  = 8'h2D;  // NOP
        mem[46]  = 8'h2E;  // NOP
        mem[47]  = 8'h2F;  // NOP
        
        // Idle loop (0x40-0x5F)
        mem[48]  = 8'h30;  // NOP
        mem[49]  = 8'h31;  // NOP
        mem[50]  = 8'h32;  // NOP
        mem[51]  = 8'h33;  // NOP
        mem[52]  = 8'h34;  // NOP
        mem[53]  = 8'h35;  // NOP
        mem[54]  = 8'h36;  // NOP
        mem[55]  = 8'h37;  // NOP
        mem[56]  = 8'h38;  // NOP
        mem[57]  = 8'h39;  // NOP
        mem[58]  = 8'h3A;  // NOP
        mem[59]  = 8'h3B;  // NOP
        mem[60]  = 8'h3C;  // NOP
        mem[61]  = 8'h3D;  // NOP
        mem[62]  = 8'h3E;  // NOP
        mem[63]  = 8'h3F;  // NOP
    end

    // ROM read
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= 8'd0;
            rdy <= 1'b1;
        end else begin
            if (addr <= 63) begin
                data_out <= mem[addr];
                rdy <= 1'b1;
            end else begin
                data_out <= 8'd0;
                rdy <= 1'b0;
            end
        end
    end

endmodule