// tb/line_buffer_tb.v — unit testbench for line_buffer (column-addressed).
// Tests write-at-column, read-at-column behaviour.
`include "params.vh"

`timescale 1ns/1ps

module line_buffer_tb;

    reg clk;
    reg rst_n;
    reg shift_en;
    reg [7:0] pixel_in;
    reg [5:0] wr_col;
    reg [5:0] rd_col;
    wire [7:0] rd_data;

    integer i;
    integer errors;

    // DUT
    line_buffer dut (
        .clk(clk),
        .rst_n(rst_n),
        .shift_en(shift_en),
        .pixel_in(pixel_in),
        .wr_col(wr_col),
        .rd_col(rd_col),
        .rd_data(rd_data)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Reference model: 32-entry array, write at wr_col, read at rd_col
    reg [7:0] ref_mem [0:31];

    initial begin
        errors = 0;
        // Reset
        rst_n = 0;
        shift_en = 0;
        pixel_in = 0;
        wr_col = 0;
        rd_col = 0;
        for (i = 0; i < 32; i = i + 1) ref_mem[i] = 0;
        @(negedge clk);
        @(negedge clk);
        rst_n = 1;

        // Test 1: write values 0..31 at columns 0..31, read back each
        for (i = 0; i < 32; i = i + 1) begin
            shift_en = 1;
            pixel_in = i + 8'd10;  // write value 10..41
            wr_col = i;
            rd_col = i;  // read same column (combinational, should show old value pre-edge)
            @(posedge clk);
            #1;
            ref_mem[i] = i + 8'd10;
            // After clock edge, rd_data should be the new value
            if (rd_data !== ref_mem[i]) begin
                $display("vec %0d: write col %0d = %0d, expected rd=%0d got rd=%0d",
                    i, i, i+10, ref_mem[i], rd_data);
                errors = errors + 1;
            end
            @(negedge clk);
        end

        // Test 2: read back all columns
        shift_en = 0;
        for (i = 0; i < 32; i = i + 1) begin
            rd_col = i;
            #1;
            if (rd_data !== ref_mem[i]) begin
                $display("read col %0d: expected %0d got %0d", i, ref_mem[i], rd_data);
                errors = errors + 1;
            end
        end

        // Test 3: overwrite a few columns
        @(negedge clk);
        shift_en = 1;
        pixel_in = 8'd99;
        wr_col = 5;
        ref_mem[5] = 8'd99;
        @(posedge clk);
        #1;
        rd_col = 5;
        if (rd_data !== 8'd99) begin
            $display("overwrite col 5: expected 99 got %0d", rd_data);
            errors = errors + 1;
        end

        // Test 4: reset clears all
        @(negedge clk);
        rst_n = 0;
        @(posedge clk);
        #1;
        for (i = 0; i < 32; i = i + 1) begin
            rd_col = i;
            #1;
            if (rd_data !== 8'd0) begin
                $display("reset: col %0d expected 0 got %0d", i, rd_data);
                errors = errors + 1;
            end
        end

        if (errors == 0)
            $display("line_buffer TEST PASSED");
        else begin
            $display("line_buffer TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule