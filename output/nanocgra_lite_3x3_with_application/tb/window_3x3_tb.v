// tb/window_3x3_tb.v — unit testbench for window_3x3.
// Vectors from golden/vectors/window_3x3.json (15 vectors).
// win is 72-bit combinational (look-ahead). window_valid is combinational.
// The shift registers are sequential (updated on posedge clk with shift_en).
`include "params.vh"

`timescale 1ns/1ps

module window_3x3_tb;

    reg clk;
    reg rst_n;
    reg shift_en;
    reg [7:0] pixel_in;
    reg [7:0] lb0_data;
    reg [7:0] lb1_data;
    reg [5:0] col_cnt;
    reg [5:0] row_cnt;
    wire [71:0] win;
    wire window_valid;

    integer i;
    integer errors;

    // DUT
    window_3x3 dut (
        .clk(clk),
        .rst_n(rst_n),
        .shift_en(shift_en),
        .pixel_in(pixel_in),
        .lb0_data(lb0_data),
        .lb1_data(lb1_data),
        .col_cnt(col_cnt),
        .row_cnt(row_cnt),
        .win(win),
        .window_valid(window_valid)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Vectors: 15 entries
    // vecs 0-8: first pass (row 0, row 1, row 2 with valid window at vec 8)
    // vecs 9-14: second pass (reset implicitly by starting over)
    // All have rst_n=1, shift_en=1.
    reg [7:0] v_pixel [0:14];
    reg [7:0] v_lb0 [0:14];
    reg [7:0] v_lb1 [0:14];
    reg [5:0] v_col [0:14];
    reg [5:0] v_row [0:14];
    reg [71:0] v_exp_win [0:14];
    reg [0:14] v_exp_valid;

    initial begin
        // vec 0: pixel=0, lb0=0, lb1=0, col=0, row=0
        v_pixel[0]=8'd0; v_lb0[0]=8'd0; v_lb1[0]=8'd0; v_col[0]=6'd0; v_row[0]=6'd0;
        v_exp_win[0]=72'd0; v_exp_valid[0]=1'b0;
        // vec 1: pixel=1, lb0=0, lb1=0, col=1, row=0
        v_pixel[1]=8'd1; v_lb0[1]=8'd0; v_lb1[1]=8'd0; v_col[1]=6'd1; v_row[1]=6'd0;
        v_exp_win[1]=72'd0; v_exp_valid[1]=1'b0;
        // vec 2: pixel=2, lb0=0, lb1=0, col=2, row=0
        v_pixel[2]=8'd2; v_lb0[2]=8'd0; v_lb1[2]=8'd0; v_col[2]=6'd2; v_row[2]=6'd0;
        v_exp_win[2]=72'd0; v_exp_valid[2]=1'b0;
        // vec 3: pixel=10, lb0=0, lb1=0, col=0, row=1
        v_pixel[3]=8'd10; v_lb0[3]=8'd0; v_lb1[3]=8'd0; v_col[3]=6'd0; v_row[3]=6'd1;
        v_exp_win[3]=72'd0; v_exp_valid[3]=1'b0;
        // vec 4: pixel=11, lb0=0, lb1=1, col=1, row=1
        v_pixel[4]=8'd11; v_lb0[4]=8'd0; v_lb1[4]=8'd1; v_col[4]=6'd1; v_row[4]=6'd1;
        v_exp_win[4]=72'd0; v_exp_valid[4]=1'b0;
        // vec 5: pixel=12, lb0=0, lb1=2, col=2, row=1
        v_pixel[5]=8'd12; v_lb0[5]=8'd0; v_lb1[5]=8'd2; v_col[5]=6'd2; v_row[5]=6'd1;
        v_exp_win[5]=72'd0; v_exp_valid[5]=1'b0;
        // vec 6: pixel=20, lb0=0, lb1=10, col=0, row=2
        v_pixel[6]=8'd20; v_lb0[6]=8'd0; v_lb1[6]=8'd10; v_col[6]=6'd0; v_row[6]=6'd2;
        v_exp_win[6]=72'd0; v_exp_valid[6]=1'b0;
        // vec 7: pixel=21, lb0=1, lb1=11, col=1, row=2
        v_pixel[7]=8'd21; v_lb0[7]=8'd1; v_lb1[7]=8'd11; v_col[7]=6'd1; v_row[7]=6'd2;
        v_exp_win[7]=72'd0; v_exp_valid[7]=1'b0;
        // vec 8: pixel=22, lb0=2, lb1=12, col=2, row=2 -> valid window
        v_pixel[8]=8'd22; v_lb0[8]=8'd2; v_lb1[8]=8'd12; v_col[8]=6'd2; v_row[8]=6'd2;
        // win = [0,1,2, 10,11,12, 20,21,22] row-major
        v_exp_win[8] = {8'd22,8'd21,8'd20,8'd12,8'd11,8'd10,8'd2,8'd1,8'd0};
        v_exp_valid[8]=1'b1;
        // vec 9-14: second pass (same as 0-5 but after the first pass shifted regs)
        v_pixel[9]=8'd0; v_lb0[9]=8'd0; v_lb1[9]=8'd0; v_col[9]=6'd0; v_row[9]=6'd0;
        v_exp_win[9]=72'd0; v_exp_valid[9]=1'b0;
        v_pixel[10]=8'd1; v_lb0[10]=8'd0; v_lb1[10]=8'd0; v_col[10]=6'd1; v_row[10]=6'd0;
        v_exp_win[10]=72'd0; v_exp_valid[10]=1'b0;
        v_pixel[11]=8'd2; v_lb0[11]=8'd0; v_lb1[11]=8'd0; v_col[11]=6'd2; v_row[11]=6'd0;
        v_exp_win[11]=72'd0; v_exp_valid[11]=1'b0;
        v_pixel[12]=8'd10; v_lb0[12]=8'd0; v_lb1[12]=8'd0; v_col[12]=6'd0; v_row[12]=6'd1;
        v_exp_win[12]=72'd0; v_exp_valid[12]=1'b0;
        v_pixel[13]=8'd11; v_lb0[13]=8'd0; v_lb1[13]=8'd1; v_col[13]=6'd1; v_row[13]=6'd1;
        v_exp_win[13]=72'd0; v_exp_valid[13]=1'b0;
        v_pixel[14]=8'd12; v_lb0[14]=8'd0; v_lb1[14]=8'd2; v_col[14]=6'd2; v_row[14]=6'd1;
        v_exp_win[14]=72'd0; v_exp_valid[14]=1'b0;

        errors = 0;
        rst_n = 0;
        shift_en = 0; pixel_in = 0; lb0_data = 0; lb1_data = 0; col_cnt = 0; row_cnt = 0;
        @(negedge clk);
        @(negedge clk);
        rst_n = 1;
        @(negedge clk);

        for (i = 0; i < 15; i = i + 1) begin
            shift_en = 1'b1;
            pixel_in = v_pixel[i];
            lb0_data = v_lb0[i];
            lb1_data = v_lb1[i];
            col_cnt = v_col[i];
            row_cnt = v_row[i];
            // win is combinational (look-ahead) — check before posedge
            #1;
            if (win !== v_exp_win[i] || window_valid !== v_exp_valid[i]) begin
                $display("vec %0d: in(pixel=%0d,lb0=%0d,lb1=%0d,col=%0d,row=%0d) expected(win_valid=%b) actual(win_valid=%b)",
                    i, v_pixel[i], v_lb0[i], v_lb1[i], v_col[i], v_row[i], v_exp_valid[i], window_valid);
                errors = errors + 1;
            end else begin
                $display("vec %0d: in(pixel=%0d,lb0=%0d,lb1=%0d,col=%0d,row=%0d) expected(win_valid=%b) actual(win_valid=%b) OK",
                    i, v_pixel[i], v_lb0[i], v_lb1[i], v_col[i], v_row[i], v_exp_valid[i], window_valid);
            end
            @(posedge clk);
            @(negedge clk);
        end

        if (errors == 0)
            $display("window_3x3 TEST PASSED");
        else begin
            $display("window_3x3 TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule