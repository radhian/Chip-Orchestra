//============================================================================
// uart.v  -  Memory-mapped UART (8N1), TX + RX, NO FIFO / NO DMA / NO IRQ.
//   Register map (selected by reg_sel[1:0] = addr[1:0]):
//     0 (0x80) TXDATA  : write -> start transmit of wdata
//     1 (0x81) RXDATA  : read  -> last received byte (read clears rx_valid)
//     2 (0x82) STATUS  : read  -> {6'b0, rx_valid, tx_busy}
//     3 (0x83) CTRL    : reserved (read 0)
//   CLK_PER_BIT parameterizes the baud generator (10 MHz / baud).
//============================================================================
`include "params.vh"

module uart #(
    parameter DW = `DATA_WIDTH,
    parameter CLK_PER_BIT = 87          // 10 MHz / 115200 ~= 87
) (
    input  wire          clk,
    input  wire          rst_n,

    // memory-mapped register interface
    input  wire          we,            // write strobe (uart selected & bus we)
    input  wire          re,            // read  strobe (uart selected & bus re)
    input  wire [1:0]    reg_sel,       // addr[1:0]
    input  wire [DW-1:0] wdata,
    output reg  [DW-1:0] rdata,

    // serial pins
    input  wire          uart_rx,       // serial input line
    output reg           uart_tx        // serial output line
);
    localparam CW = 16;                 // baud counter width

    // ---------------- Transmitter (8N1) -------------------------------
    localparam TX_IDLE = 2'd0, TX_START = 2'd1, TX_DATA = 2'd2, TX_STOP = 2'd3;
    reg [1:0]     tx_state;
    reg [CW-1:0]  tx_cnt;
    reg [2:0]     tx_bit;
    reg [DW-1:0]  tx_shift;
    reg           tx_busy;
    reg           tx_start;

    always @(posedge clk) begin
        if (!rst_n) begin
            tx_state <= TX_IDLE;
            tx_cnt   <= {CW{1'b0}};
            tx_bit   <= 3'd0;
            tx_shift <= {DW{1'b0}};
            tx_busy  <= 1'b0;
            uart_tx  <= 1'b1;           // idle high
        end else begin
            case (tx_state)
                TX_IDLE: begin
                    uart_tx <= 1'b1;
                    tx_cnt  <= {CW{1'b0}};
                    tx_bit  <= 3'd0;
                    if (tx_start) begin
                        tx_shift <= wdata;
                        tx_busy  <= 1'b1;
                        tx_state <= TX_START;
                    end else begin
                        tx_busy  <= 1'b0;
                    end
                end
                TX_START: begin
                    uart_tx <= 1'b0;    // start bit
                    if (tx_cnt == CLK_PER_BIT-1) begin
                        tx_cnt   <= {CW{1'b0}};
                        tx_state <= TX_DATA;
                    end else tx_cnt <= tx_cnt + 1'b1;
                end
                TX_DATA: begin
                    uart_tx <= tx_shift[0];
                    if (tx_cnt == CLK_PER_BIT-1) begin
                        tx_cnt   <= {CW{1'b0}};
                        tx_shift <= {1'b0, tx_shift[DW-1:1]};
                        if (tx_bit == 3'd7) begin
                            tx_state <= TX_STOP;
                        end else tx_bit <= tx_bit + 1'b1;
                    end else tx_cnt <= tx_cnt + 1'b1;
                end
                TX_STOP: begin
                    uart_tx <= 1'b1;    // stop bit
                    if (tx_cnt == CLK_PER_BIT-1) begin
                        tx_cnt   <= {CW{1'b0}};
                        tx_busy  <= 1'b0;
                        tx_state <= TX_IDLE;
                    end else tx_cnt <= tx_cnt + 1'b1;
                end
                default: tx_state <= TX_IDLE;
            endcase
        end
    end

    // fire a one-cycle transmit request when TXDATA is written and idle
    always @(*) tx_start = we && (reg_sel == 2'd0) && !tx_busy;

    // ---------------- Receiver (8N1) ----------------------------------
    localparam RX_IDLE = 2'd0, RX_START = 2'd1, RX_DATA = 2'd2, RX_STOP = 2'd3;
    reg [1:0]     rx_state;
    reg [CW-1:0]  rx_cnt;
    reg [2:0]     rx_bit;
    reg [DW-1:0]  rx_shift;
    reg [DW-1:0]  rx_data;
    reg           rx_valid;
    reg           rx_sync0, rx_sync1;   // 2-FF synchronizer

    always @(posedge clk) begin
        if (!rst_n) begin
            rx_sync0 <= 1'b1;
            rx_sync1 <= 1'b1;
        end else begin
            rx_sync0 <= uart_rx;
            rx_sync1 <= rx_sync0;
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            rx_state <= RX_IDLE;
            rx_cnt   <= {CW{1'b0}};
            rx_bit   <= 3'd0;
            rx_shift <= {DW{1'b0}};
            rx_data  <= {DW{1'b0}};
            rx_valid <= 1'b0;
        end else begin
            // reading RXDATA clears the valid flag
            if (re && (reg_sel == 2'd1))
                rx_valid <= 1'b0;

            case (rx_state)
                RX_IDLE: begin
                    rx_cnt <= {CW{1'b0}};
                    rx_bit <= 3'd0;
                    if (rx_sync1 == 1'b0) begin        // start bit edge
                        rx_state <= RX_START;
                    end
                end
                RX_START: begin
                    if (rx_cnt == (CLK_PER_BIT/2)) begin // sample mid start
                        rx_cnt   <= {CW{1'b0}};
                        rx_state <= RX_DATA;
                    end else rx_cnt <= rx_cnt + 1'b1;
                end
                RX_DATA: begin
                    if (rx_cnt == CLK_PER_BIT-1) begin
                        rx_cnt   <= {CW{1'b0}};
                        rx_shift <= {rx_sync1, rx_shift[DW-1:1]};
                        if (rx_bit == 3'd7) begin
                            rx_state <= RX_STOP;
                        end else rx_bit <= rx_bit + 1'b1;
                    end else rx_cnt <= rx_cnt + 1'b1;
                end
                RX_STOP: begin
                    if (rx_cnt == CLK_PER_BIT-1) begin
                        rx_cnt   <= {CW{1'b0}};
                        rx_data  <= rx_shift;
                        rx_valid <= 1'b1;
                        rx_state <= RX_IDLE;
                    end else rx_cnt <= rx_cnt + 1'b1;
                end
                default: rx_state <= RX_IDLE;
            endcase
        end
    end

    // ---------------- Register read mux -------------------------------
    always @(*) begin
        case (reg_sel)
            2'd0:    rdata = tx_shift;                         // TXDATA (rd-back)
            2'd1:    rdata = rx_data;                          // RXDATA
            2'd2:    rdata = {{(DW-2){1'b0}}, rx_valid, tx_busy}; // STATUS
            default: rdata = {DW{1'b0}};                       // CTRL/reserved
        endcase
    end
endmodule
