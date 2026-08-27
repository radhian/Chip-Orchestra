// tb/nano_controller_tb.v — unit testbench for nano_controller.
// Vectors from golden/vectors/nano_controller.json (7 vectors).
// Sequential module: outputs are registered, checked after posedge.
`include "params.vh"

`timescale 1ns/1ps

module nano_controller_tb;

    reg clk;
    reg rst_n;
    reg [7:0] rx_byte;
    reg rx_valid;
    reg tx_done;
    reg cgra_done;
    reg [7:0] sobel_out;
    wire [7:0] bus_addr;
    wire bus_wr;
    wire bus_rd;
    wire [7:0] bus_wdata;
    wire [7:0] pixel_in;
    wire pixel_shift;
    wire [5:0] col_cnt;
    wire [5:0] row_cnt;
    wire start_cgra;
    wire tx_start;
    wire [7:0] tx_data;
    wire [7:0] status;

    integer i;
    integer errors;

    // DUT
    nano_controller dut (
        .clk(clk),
        .rst_n(rst_n),
        .rx_byte(rx_byte),
        .rx_valid(rx_valid),
        .tx_done(tx_done),
        .cgra_done(cgra_done),
        .sobel_out(sobel_out),
        .bus_addr(bus_addr),
        .bus_wr(bus_wr),
        .bus_rd(bus_rd),
        .bus_wdata(bus_wdata),
        .pixel_in(pixel_in),
        .pixel_shift(pixel_shift),
        .col_cnt(col_cnt),
        .row_cnt(row_cnt),
        .start_cgra(start_cgra),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .status(status)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Vectors: 7 entries
    // vecs 0-5: rst_n=1, rx_valid=1, rx_byte=66,0,1,2,3,4
    // vec 6: rst_n=0 -> all zeros
    reg [0:6] v_rst_n = 7'b1111110;
    reg [7:0] v_rx_byte [0:6];
    reg [0:6] v_rx_valid = 7'b1111110;
    reg [0:6] v_tx_done = 7'b0000000;
    reg [0:6] v_cgra_done = 7'b0000000;
    reg [7:0] v_sobel_out [0:6];
    // Expected outputs
    reg [7:0] v_exp_pixel_in [0:6];
    reg [0:6] v_exp_pixel_shift;
    reg [5:0] v_exp_col [0:6];
    reg [5:0] v_exp_row [0:6];
    reg [0:6] v_exp_tx_start;
    reg [7:0] v_exp_tx_data [0:6];
    reg [7:0] v_exp_status [0:6];

    initial begin
        // vec 0: rx_byte=66, rx_valid=1 -> pixel_in=66, pixel_shift=1, col=1, row=0
        v_rx_byte[0]=8'd66; v_sobel_out[0]=8'd0;
        v_exp_pixel_in[0]=8'd66; v_exp_pixel_shift[0]=1'b1; v_exp_col[0]=6'd1; v_exp_row[0]=6'd0;
        v_exp_tx_start[0]=1'b0; v_exp_tx_data[0]=8'd0; v_exp_status[0]=8'd0;
        // vec 1: rx_byte=0, rx_valid=1 -> pixel_in=0, pixel_shift=1, col=2, row=0
        v_rx_byte[1]=8'd0; v_sobel_out[1]=8'd0;
        v_exp_pixel_in[1]=8'd0; v_exp_pixel_shift[1]=1'b1; v_exp_col[1]=6'd2; v_exp_row[1]=6'd0;
        v_exp_tx_start[1]=1'b0; v_exp_tx_data[1]=8'd0; v_exp_status[1]=8'd0;
        // vec 2: rx_byte=1, rx_valid=1 -> pixel_in=1, pixel_shift=1, col=3, row=0
        v_rx_byte[2]=8'd1; v_sobel_out[2]=8'd0;
        v_exp_pixel_in[2]=8'd1; v_exp_pixel_shift[2]=1'b1; v_exp_col[2]=6'd3; v_exp_row[2]=6'd0;
        v_exp_tx_start[2]=1'b0; v_exp_tx_data[2]=8'd0; v_exp_status[2]=8'd0;
        // vec 3: rx_byte=2, rx_valid=1 -> pixel_in=2, pixel_shift=1, col=4, row=0
        v_rx_byte[3]=8'd2; v_sobel_out[3]=8'd0;
        v_exp_pixel_in[3]=8'd2; v_exp_pixel_shift[3]=1'b1; v_exp_col[3]=6'd4; v_exp_row[3]=6'd0;
        v_exp_tx_start[3]=1'b0; v_exp_tx_data[3]=8'd0; v_exp_status[3]=8'd0;
        // vec 4: rx_byte=3, rx_valid=1 -> pixel_in=3, pixel_shift=1, col=5, row=0
        v_rx_byte[4]=8'd3; v_sobel_out[4]=8'd0;
        v_exp_pixel_in[4]=8'd3; v_exp_pixel_shift[4]=1'b1; v_exp_col[4]=6'd5; v_exp_row[4]=6'd0;
        v_exp_tx_start[4]=1'b0; v_exp_tx_data[4]=8'd0; v_exp_status[4]=8'd0;
        // vec 5: rx_byte=4, rx_valid=1 -> pixel_in=4, pixel_shift=1, col=6, row=0
        v_rx_byte[5]=8'd4; v_sobel_out[5]=8'd0;
        v_exp_pixel_in[5]=8'd4; v_exp_pixel_shift[5]=1'b1; v_exp_col[5]=6'd6; v_exp_row[5]=6'd0;
        v_exp_tx_start[5]=1'b0; v_exp_tx_data[5]=8'd0; v_exp_status[5]=8'd0;
        // vec 6: rst_n=0 -> all zeros
        v_rx_byte[6]=8'd0; v_sobel_out[6]=8'd0;
        v_exp_pixel_in[6]=8'd0; v_exp_pixel_shift[6]=1'b0; v_exp_col[6]=6'd0; v_exp_row[6]=6'd0;
        v_exp_tx_start[6]=1'b0; v_exp_tx_data[6]=8'd0; v_exp_status[6]=8'd0;

        errors = 0;
        rst_n = 0;
        rx_byte = 0; rx_valid = 0; tx_done = 0; cgra_done = 0; sobel_out = 0;
        @(negedge clk);
        @(negedge clk);

        for (i = 0; i < 7; i = i + 1) begin
            rst_n = v_rst_n[i];
            rx_byte = v_rx_byte[i];
            rx_valid = v_rx_valid[i];
            tx_done = v_tx_done[i];
            cgra_done = v_cgra_done[i];
            sobel_out = v_sobel_out[i];
            @(posedge clk);
            #1;
            if (pixel_in !== v_exp_pixel_in[i] ||
                pixel_shift !== v_exp_pixel_shift[i] ||
                col_cnt !== v_exp_col[i] ||
                row_cnt !== v_exp_row[i] ||
                tx_start !== v_exp_tx_start[i] ||
                tx_data !== v_exp_tx_data[i] ||
                status !== v_exp_status[i]) begin
                $display("vec %0d: in(rx_byte=%0d,rx_valid=%b,rst_n=%b)", i, v_rx_byte[i], v_rx_valid[i], v_rst_n[i]);
                $display("  expected: pixel_in=%0d pixel_shift=%b col=%0d row=%0d tx_start=%b tx_data=%0d status=%0d",
                    v_exp_pixel_in[i], v_exp_pixel_shift[i], v_exp_col[i], v_exp_row[i],
                    v_exp_tx_start[i], v_exp_tx_data[i], v_exp_status[i]);
                $display("  actual:   pixel_in=%0d pixel_shift=%b col=%0d row=%0d tx_start=%b tx_data=%0d status=%0d",
                    pixel_in, pixel_shift, col_cnt, row_cnt, tx_start, tx_data, status);
                errors = errors + 1;
            end else begin
                $display("vec %0d: in(rx_byte=%0d,rx_valid=%b,rst_n=%b) expected(pixel_in=%0d,col=%0d) actual(pixel_in=%0d,col=%0d) OK",
                    i, v_rx_byte[i], v_rx_valid[i], v_rst_n[i], v_exp_pixel_in[i], v_exp_col[i], pixel_in, col_cnt);
            end
            @(negedge clk);
        end

        if (errors == 0)
            $display("nano_controller TEST PASSED");
        else begin
            $display("nano_controller TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule