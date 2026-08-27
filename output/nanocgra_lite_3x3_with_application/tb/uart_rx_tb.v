// tb/uart_rx_tb.v — unit testbench for uart_rx.
// Vectors from golden/vectors/uart_rx.json (17365 vectors).
// Uses $readmemh files for compact data storage.
// Drives rx_in from the vector file, checks rx_valid and rx_byte.
`include "params.vh"

`timescale 1ns/1ps

module uart_rx_tb;

    reg clk;
    reg rst_n;
    reg rx_in;
    wire [7:0] rx_byte;
    wire rx_valid;

    integer i;
    integer errors;

    // DUT
    uart_rx dut (
        .clk(clk),
        .rst_n(rst_n),
        .rx_in(rx_in),
        .rx_byte(rx_byte),
        .rx_valid(rx_valid)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Vector data loaded from mem files
    reg [0:0] v_rx_in [0:17364];
    reg [0:0] v_rst [0:17364];
    reg [0:0] v_exp_valid [0:17364];
    reg [7:0] v_exp_byte [0:17364];
    reg [0:0] v_byte_mask [0:17364];

    initial begin
        $readmemh("tb/vecs/uart_rx_in.mem", v_rx_in);
        $readmemh("tb/vecs/uart_rx_rst.mem", v_rst);
        $readmemh("tb/vecs/uart_rx_exp_valid.mem", v_exp_valid);
        $readmemh("tb/vecs/uart_rx_exp_byte.mem", v_exp_byte);
        $readmemh("tb/vecs/uart_rx_byte_mask.mem", v_byte_mask);

        errors = 0;
        rst_n = 0;
        rx_in = 1;
        @(negedge clk);
        @(negedge clk);

        for (i = 0; i < 17365; i = i + 1) begin
            rst_n = v_rst[i];
            rx_in = v_rx_in[i];
            @(posedge clk);
            #1;
            // Check rx_valid
            if (rx_valid !== v_exp_valid[i]) begin
                $display("vec %0d: in(rx_in=%b,rst_n=%b) expected(rx_valid=%b) actual(rx_valid=%b)",
                    i, v_rx_in[i], v_rst[i], v_exp_valid[i], rx_valid);
                errors = errors + 1;
                if (errors > 20) begin
                    $display("Too many errors, stopping");
                    $fatal(1);
                end
            end
            // Check rx_byte when mask is set
            if (v_byte_mask[i] == 1'b1 && rx_byte !== v_exp_byte[i]) begin
                $display("vec %0d: in(rx_in=%b,rst_n=%b) expected(rx_byte=%0d) actual(rx_byte=%0d)",
                    i, v_rx_in[i], v_rst[i], v_exp_byte[i], rx_byte);
                errors = errors + 1;
                if (errors > 20) begin
                    $display("Too many errors, stopping");
                    $fatal(1);
                end
            end
            // Display on valid pulse or byte check
            if (v_exp_valid[i] == 1'b1 || v_byte_mask[i] == 1'b1) begin
                $display("vec %0d: in(rx_in=%b) expected(valid=%b,byte=%0d) actual(valid=%b,byte=%0d) OK",
                    i, v_rx_in[i], v_exp_valid[i], v_exp_byte[i], rx_valid, rx_byte);
            end
            @(negedge clk);
        end

        if (errors == 0)
            $display("uart_rx TEST PASSED");
        else begin
            $display("uart_rx TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule