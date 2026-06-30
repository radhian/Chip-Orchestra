`timescale 1ns/1ps

module uart_regs
(
    input  wire         clk,
    input  wire         rst_n,

    // Bus Interface
    input  wire         bus_valid,
    input  wire         bus_write,
    input  wire [31:0]  bus_addr,
    input  wire [31:0]  bus_wdata,

    output reg  [31:0]  bus_rdata,
    output wire         bus_ready,

    //--------------------------------------------------
    // TX FIFO
    //--------------------------------------------------

    output reg          tx_push,
    output reg [7:0]    tx_data,
    input  wire         tx_full,
    input  wire         tx_empty,

    //--------------------------------------------------
    // RX FIFO
    //--------------------------------------------------

    output reg          rx_pop,
    input  wire [7:0]   rx_data,
    input  wire         rx_empty,
    input  wire         rx_full,

    //--------------------------------------------------
    // UART Status
    //--------------------------------------------------

    input wire          tx_busy,
    input wire          framing_error,
    input wire          overflow,

    //--------------------------------------------------
    // Outputs
    //--------------------------------------------------

    output reg          uart_enable,
    output reg          tx_enable,
    output reg          rx_enable,

    output reg [15:0]   baud_div,

    output reg [3:0]    irq_enable
);

assign bus_ready = 1'b1;

////////////////////////////////////////////////////////////
// Registers
////////////////////////////////////////////////////////////

reg [3:0] irq_status;

localparam REG_TXDATA     = 5'h00;
localparam REG_RXDATA     = 5'h04;
localparam REG_STATUS     = 5'h08;
localparam REG_CTRL       = 5'h0C;
localparam REG_BAUD       = 5'h10;
localparam REG_IRQ_STATUS = 5'h14;
localparam REG_IRQ_ENABLE = 5'h18;

wire [4:0] reg_addr;

assign reg_addr = bus_addr[4:0];

////////////////////////////////////////////////////////////
// Write Logic
////////////////////////////////////////////////////////////

always @(posedge clk or negedge rst_n)
begin

    if(!rst_n)
    begin

        uart_enable <= 1'b0;
        tx_enable   <= 1'b0;
        rx_enable   <= 1'b0;

        baud_div    <= 16'd174;

        irq_enable  <= 4'd0;

        tx_push <= 1'b0;
        rx_pop  <= 1'b0;

    end
    else
    begin

        tx_push <= 1'b0;
        rx_pop  <= 1'b0;

        if(bus_valid && bus_write)
        begin

            case(reg_addr)

            REG_TXDATA:
            begin
                if(!tx_full)
                begin
                    tx_push <= 1'b1;
                    tx_data <= bus_wdata[7:0];
                end
            end

            REG_CTRL:
            begin
                uart_enable <= bus_wdata[0];
                tx_enable   <= bus_wdata[1];
                rx_enable   <= bus_wdata[2];
            end

            REG_BAUD:
                baud_div <= bus_wdata[15:0];

            REG_IRQ_ENABLE:
                irq_enable <= bus_wdata[3:0];

            REG_IRQ_STATUS:
                irq_status <= irq_status & ~bus_wdata[3:0];

            default:

            begin
            end

            endcase

        end

        if(bus_valid && !bus_write)
        begin
            if(reg_addr == REG_RXDATA && !rx_empty)
                rx_pop <= 1'b1;
        end

    end

end

////////////////////////////////////////////////////////////
// Read Logic
////////////////////////////////////////////////////////////

always @(*)
begin

    bus_rdata = 32'd0;

    case(reg_addr)

    REG_RXDATA:
        bus_rdata = {24'd0, rx_data};

    REG_STATUS:
        bus_rdata =
        {
            24'd0,
            rx_full,
            tx_full,
            framing_error,
            overflow,
            !rx_empty,
            tx_empty,
            tx_busy,
            uart_enable
        };

    REG_CTRL:
        bus_rdata =
        {
            29'd0,
            rx_enable,
            tx_enable,
            uart_enable
        };

    REG_BAUD:
        bus_rdata = {16'd0, baud_div};

    REG_IRQ_ENABLE:
        bus_rdata = {28'd0, irq_enable};

    REG_IRQ_STATUS:
        bus_rdata = {28'd0, irq_status};

    default:
        bus_rdata = 32'd0;

    endcase

end

endmodule