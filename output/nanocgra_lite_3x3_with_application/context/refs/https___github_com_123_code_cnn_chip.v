// ===== cnn_chip/uart_rx.v =====
module uart_rx #(
    parameter CLK_FREQ = 27000000,
    parameter BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx_in,
    output reg  [7:0] rx_byte,
    output reg        rx_valid
);

    localparam BIT_TICK = CLK_FREQ / BAUD_RATE;
    localparam HALF_TICK = BIT_TICK / 2;

    localparam IDLE  = 2'b00;
    localparam START = 2'b01;
    localparam DATA  = 2'b10;
    localparam STOP  = 2'b11;

    reg [1:0] state;
    reg [15:0] tick_counter;
    reg [2:0] bit_index;
    reg [7:0] shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            tick_counter <= 0;
            bit_index <= 0;
            shift_reg <= 0;
            rx_byte <= 0;
            rx_valid <= 0;
        end else begin
            rx_valid <= 0; // Default to 0, only pulse high for 1 cycle

            case (state)
                IDLE: begin
                    if (rx_in == 1'b0) begin // Start bit detected
                        state <= START;
                        tick_counter <= 0;
                    end
                end
                
                START: begin
                    if (tick_counter == HALF_TICK) begin
                        if (rx_in == 1'b0) begin // Confirm it's still 0
                            state <= DATA;
                            tick_counter <= 0;
                            bit_index <= 0;
                        end else begin
                            state <= IDLE; // False alarm
                        end
                    end else begin
                        tick_counter <= tick_counter + 1;
                    end
                end
                
                DATA: begin
                    if (tick_counter == BIT_TICK - 1) begin
                        tick_counter <= 0;
                        shift_reg[bit_index] <= rx_in; // Sample data
                        
                        if (bit_index == 7) begin
                            state <= STOP;
                        end else begin
                            bit_index <= bit_index + 1;
                        end
                    end else begin
                        tick_counter <= tick_counter + 1;
                    end
                end
                
                STOP: begin
                    if (tick_counter == BIT_TICK - 1) begin
                        state <= IDLE;
                        rx_byte <= shift_reg;
                        rx_valid <= 1'b1; // Output valid byte
                    end else begin
                        tick_counter <= tick_counter + 1;
                    end
                end
                
                default: state <= IDLE;
            endcase
        end
    end
endmodule

// ===== cnn_chip/uart_tx.v =====
module uart_tx #(
    parameter CLK_FREQ = 27000000,
    parameter BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] data_in,
    output reg        tx_out,
    output reg        tx_done
);

    localparam BIT_TICK = CLK_FREQ / BAUD_RATE;

    localparam IDLE  = 2'b00;
    localparam START = 2'b01;
    localparam DATA  = 2'b10;
    localparam STOP  = 2'b11;

    reg [1:0] state;
    reg [15:0] tick_counter;
    reg [2:0] bit_index;
    reg [7:0] shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            tick_counter <= 0;
            bit_index <= 0;
            shift_reg <= 0;
            tx_out <= 1'b1; // UART line rests HIGH
            tx_done <= 0;
        end else begin
            tx_done <= 0;

            case (state)
                IDLE: begin
                    tx_out <= 1'b1;
                    if (tx_start) begin
                        state <= START;
                        shift_reg <= data_in;
                        tick_counter <= 0;
                    end
                end
                
                START: begin
                    tx_out <= 1'b0; // Start bit is LOW
                    if (tick_counter == BIT_TICK - 1) begin
                        state <= DATA;
                        tick_counter <= 0;
                        bit_index <= 0;
                    end else begin
                        tick_counter <= tick_counter + 1;
                    end
                end
                
                DATA: begin
                    tx_out <= shift_reg[bit_index]; // Send LSB first
                    if (tick_counter == BIT_TICK - 1) begin
                        tick_counter <= 0;
                        if (bit_index == 7) begin
                            state <= STOP;
                        end else begin
                            bit_index <= bit_index + 1;
                        end
                    end else begin
                        tick_counter <= tick_counter + 1;
                    end
                end
                
                STOP: begin
                    tx_out <= 1'b1; // Stop bit is HIGH
                    if (tick_counter == BIT_TICK - 1) begin
                        state <= IDLE;
                        tx_done <= 1'b1;
                    end else begin
                        tick_counter <= tick_counter + 1;
                    end
                end
                
                default: state <= IDLE;
            endcase
        end
    end
endmodule

// ===== cnn_chip/control_unit.v =====
module control_unit (
    input  wire clk,
    input  wire rst_n,
    
    input  wire rx_byte_valid,
    input  wire layer_done,
    input  wire tx_done,
    
    output wire sram_write_en,
    output reg  start_layer,
    output reg  tx_start
);

    // Combinational: write happens on the SAME cycle as rx_byte_valid,
    // so byte_counter (pre-edge) is the correct write address.
    assign sram_write_en = rx_byte_valid;

    localparam [1:0] S_IDLE      = 2'd0,
                     S_LOAD_IMG  = 2'd1,
                     S_COMPUTE   = 2'd2,
                     S_TX_RESULT = 2'd3;

    reg [1:0] current_state, next_state;
    reg [9:0] byte_counter; 

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state <= S_IDLE;
            byte_counter  <= 10'd0;
        end else begin
            current_state <= next_state;
            if (rx_byte_valid) byte_counter <= byte_counter + 1'b1;
            if (current_state == S_TX_RESULT && tx_done) byte_counter <= 10'd0; 
        end
    end

    always @(*) begin
        next_state = current_state; 
        case (current_state)
            S_IDLE:      if (rx_byte_valid) next_state = S_LOAD_IMG;
            S_LOAD_IMG:  if (byte_counter == 10'd783 && rx_byte_valid) next_state = S_COMPUTE;
            S_COMPUTE:   if (layer_done) next_state = S_TX_RESULT;
            S_TX_RESULT: if (tx_done) next_state = S_IDLE;
            default: next_state = S_IDLE;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            start_layer <= 1'b0; tx_start <= 1'b0;
        end else begin
            start_layer <= 1'b0; tx_start <= 1'b0;

            case (next_state)
                S_COMPUTE:   start_layer <= 1'b1; // Turns ON the whole pipeline
                S_TX_RESULT: if (current_state != S_TX_RESULT) tx_start <= 1'b1;
            endcase
        end
    end
endmodule

// ===== cnn_chip/top_loopback.v =====
// LOOPBACK TEST — replaces top_mnist_accel temporarily.
// Whatever byte the PC sends should come back unchanged.
// If this works, BL616 UART bridge is OK and our chip is the problem.
// If silent, BL616 bridge is broken (need different USB serial path).

module top_mnist_accel (
    input  wire clk,
    input  wire rst_n,
    input  wire uart_rx_pin,
    output wire uart_tx_pin
);
    assign uart_tx_pin = uart_rx_pin;
endmodule


// ===== cnn_chip/mem_image_ram.v =====
module mem_image_ram (
    input  wire        clk,
    
    // Write Port (Used by the FSM / UART RX)
    input  wire        write_en,
    input  wire [9:0]  write_addr,
    input  wire [7:0]  data_in,
    
    // Read Port (Used by the Compute Pipeline)
    input  wire [9:0]  read_addr,
    output reg  [7:0]  data_out
);

    // Create the memory array: 784 slots, each 8 bits wide
    reg [7:0] ram [0:783];

    // Synchronous Read/Write logic
    always @(posedge clk) begin
        if (write_en) begin
            ram[write_addr] <= data_in;
        end
        
        // The read happens on the clock edge, perfectly matching 
        // the 1-cycle latency of a real hardware BRAM.
        data_out <= ram[read_addr];
    end

endmodule

// ===== cnn_chip/mem_weights_rom.v =====
module mem_weights_rom (
    input  wire        clk,
    input  wire [15:0] read_addr,       // weight address (0..1698)
    input  wire [3:0]  bias_addr,       // bias address  (0..10; 0 unused, 1..10 = FC b