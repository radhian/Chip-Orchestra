module uart (
    input  wire                    clk,
    input  wire                    rst_n,
    input  wire                    tx_en,   // TX enable
    input  wire [7:0]              tx_data,  // TX data
    input  wire                    rx_en,   // RX enable
    input  wire [7:0]              rx_data,  // RX data
    output reg                     tx_ready, // TX ready
    output reg                     rx_ready, // RX ready
    output reg                     tx_busy,  // TX busy
    output reg                     rx_busy,  // RX busy
    output reg                     status,   // Status register
    output reg                     ctrl      // Control register
);

    // UART registers
    reg [7:0]                    tx_shift_reg;
    reg [7:0]                    rx_shift_reg;
    reg [7:0]                    tx_buffer;
    reg [7:0]                    rx_buffer;
    reg [7:0]                    status_reg;
    reg [7:0]                    ctrl_reg;
    
    // Baud rate counter (115200 baud at 10 MHz = ~87 clock cycles per bit)
    reg [15:0]                  baud_counter;
    reg                         baud_done;
    
    // TX state machine
    reg [2:0]                    tx_state;
    localparam TX_IDLE         = 3'b000;
    localparam TX_SHIFT        = 3'b001;
    localparam TX_COMPLETE     = 3'b010;
    
    // RX state machine
    reg [2:0]                    rx_state;
    localparam RX_IDLE         = 3'b000;
    localparam RX_SHIFT        = 3'b001;
    localparam RX_COMPLETE     = 3'b010;

    // TX state machine
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_state <= TX_IDLE;
            tx_shift_reg <= 8'd0;
            tx_buffer <= 8'd0;
            tx_ready <= 1'b1;
            tx_busy <= 1'b0;
        end else begin
            case (tx_state)
                TX_IDLE: begin
                    if (tx_en) begin
                        tx_state <= TX_SHIFT;
                        tx_shift_reg <= tx_data;
                        tx_buffer <= tx_data;
                        tx_ready <= 1'b0;
                        tx_busy <= 1'b1;
                    end
                end
                
                TX_SHIFT: begin
                    baud_counter <= baud_counter + 16'd1;
                    
                    if (baud_done) begin
                        tx_shift_reg <= {tx_shift_reg[6:0], 1'b0};
                        baud_counter <= 16'd0;
                        baud_done <= 1'b0;
                        
                        if (tx_shift_reg[0] == 1'b1) begin
                            status_reg <= status_reg | 8'h80;  // TXE flag
                        end
                        
                        if (tx_shift_reg[0] == 1'b0) begin
                            status_reg <= status_reg & ~8'h80;
                        end
                        
                        if (tx_shift_reg == 8'd0) begin
                            tx_state <= TX_COMPLETE;
                            tx_busy <= 1'b0;
                            tx_ready <= 1'b1;
                        end
                    end
                end
                
                TX_COMPLETE: begin
                    tx_state <= TX_IDLE;
                    tx_shift_reg <= 8'd0;
                    tx_buffer <= 8'd0;
                    tx_busy <= 1'b0;
                    tx_ready <= 1'b1;
                end
            endcase
        end
    end

    // RX state machine
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_state <= RX_IDLE;
            rx_shift_reg <= 8'd0;
            rx_buffer <= 8'd0;
            rx_ready <= 1'b1;
            rx_busy <= 1'b0;
        end else begin
            case (rx_state)
                RX_IDLE: begin
                    if (rx_en) begin
                        rx_state <= RX_SHIFT;
                        rx_shift_reg <= rx_data;
                        rx_buffer <= rx_data;
                        rx_ready <= 1'b0;
                        rx_busy <= 1'b1;
                    end
                end
                
                RX_SHIFT: begin
                    baud_counter <= baud_counter + 16'd1;
                    
                    if (baud_done) begin
                        rx_shift_reg <= {rx_shift_reg[6:0], 1'b0};
                        baud_counter <= 16'd0;
                        baud_done <= 1'b0;
                        
                        if (rx_shift_reg == 8'd0) begin
                            rx_state <= RX_COMPLETE;
                            rx_busy <= 1'b0;
                            rx_ready <= 1'b1;
                        end
                    end
                end
                
                RX_COMPLETE: begin
                    rx_state <= RX_IDLE;
                    rx_shift_reg <= 8'd0;
                    rx_buffer <= 8'd0;
                    rx_ready <= 1'b1;
                end
            endcase
        end
    end

    // Status register
    // Bit 7: TXE (Transmit Empty)
    // Bit 6: RXNE (Receive Not Empty)
    // Bit 5: PE (Parity Error)
    // Bit 4: FE (Framing Error)
    // Bit 3: OE (Overrun Error)
    // Bits 2-0: Reserved
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            status <= 8'h00;
        end else begin
            status <= status_reg;
        end
    end

    // Control register
    // Bit 7: TXE (Enable TX)
    // Bit 6: RXE (Enable RX)
    // Bits 5-0: Reserved
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ctrl <= 8'h00;
        end else begin
            ctrl <= ctrl_reg;
        end
    end

    // Baud rate counter reset
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            baud_done <= 1'b0;
        end else begin
            baud_done <= 1'b1;
        end
    end

endmodule