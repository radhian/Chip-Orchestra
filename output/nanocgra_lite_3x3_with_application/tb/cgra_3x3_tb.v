// tb/cgra_3x3_tb.v — unit testbench for cgra_3x3.
// Vectors from golden/vectors/cgra_3x3.json (16 vectors).
// Combinational outputs (sobel_out, done=start).
`include "params.vh"

`timescale 1ns/1ps

module cgra_3x3_tb;

    reg clk;
    reg rst_n;
    reg [71:0] win;
    reg start;
    wire [7:0] sobel_out;
    wire done;

    integer i;
    integer errors;

    // DUT
    cgra_3x3 dut (
        .clk(clk),
        .rst_n(rst_n),
        .win(win),
        .start(start),
        .sobel_out(sobel_out),
        .done(done)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Vectors: 16 windows
    reg [71:0] v_win [0:15];
    reg [0:15] v_rst_n = 16'b1111111111111110;
    reg [0:15] v_start = 16'b1111111111111110;
    reg [7:0] v_exp [0:15];
    reg [0:15] v_exp_done = 16'b1111111111111110;

    initial begin
        // vec 0: [100]*9 -> 0
        v_win[0]  = {8'd100,8'd100,8'd100,8'd100,8'd100,8'd100,8'd100,8'd100,8'd100}; v_exp[0]=8'd0;
        // vec 1: [0,0,255,0,0,255,0,0,255] -> 255
        v_win[1]  = {8'd255,8'd0,8'd255,8'd0,8'd0,8'd255,8'd0,8'd0,8'd0}; v_exp[1]=8'd255;
        // vec 2: [0,0,0,0,0,0,255,255,255] -> 255
        v_win[2]  = {8'd255,8'd255,8'd255,8'd0,8'd0,8'd0,8'd0,8'd0,8'd0}; v_exp[2]=8'd255;
        // vec 3: [132,148,95,118,75,115,95,66,36] -> 255
        v_win[3]  = {8'd36,8'd66,8'd95,8'd115,8'd75,8'd118,8'd95,8'd148,8'd132}; v_exp[3]=8'd255;
        // vec 4: [109,150,15,220,64,7,141,75,43] -> 255
        v_win[4]  = {8'd43,8'd75,8'd141,8'd7,8'd64,8'd220,8'd15,8'd150,8'd109}; v_exp[4]=8'd255;
        // vec 5: [134,230,223,71,131,182,119,249,219] -> 255
        v_win[5]  = {8'd219,8'd249,8'd119,8'd182,8'd131,8'd71,8'd223,8'd230,8'd134}; v_exp[5]=8'd255;
        // vec 6: [186,220,160,60,177,134,229,69,225] -> 255
        v_win[6]  = {8'd225,8'd69,8'd229,8'd134,8'd177,8'd60,8'd160,8'd220,8'd186}; v_exp[6]=8'd255;
        // vec 7: [227,90,150,103,91,182,129,190,235] -> 255
        v_win[7]  = {8'd235,8'd190,8'd129,8'd182,8'd91,8'd103,8'd150,8'd90,8'd227}; v_exp[7]=8'd255;
        // vec 8: [134,143,202,66,251,120,120,99,187] -> 255
        v_win[8]  = {8'd187,8'd99,8'd120,8'd120,8'd251,8'd66,8'd202,8'd143,8'd134}; v_exp[8]=8'd255;
        // vec 9: [67,37,220,237,199,1,217,22,115] -> 255
        v_win[9]  = {8'd115,8'd22,8'd217,8'd1,8'd199,8'd237,8'd220,8'd37,8'd67}; v_exp[9]=8'd255;
        // vec 10: [72,254,227,129,81,211,128,179,103] -> 255
        v_win[10] = {8'd103,8'd179,8'd128,8'd211,8'd81,8'd129,8'd227,8'd254,8'd72}; v_exp[10]=8'd255;
        // vec 11: [191,70,121,254,108,21,19,183,174] -> 255
        v_win[11] = {8'd174,8'd183,8'd19,8'd21,8'd108,8'd254,8'd121,8'd70,8'd191}; v_exp[11]=8'd255;
        // vec 12: [93,151,98,84,57,115,85,35,219] -> 255
        v_win[12] = {8'd219,8'd35,8'd85,8'd115,8'd57,8'd84,8'd98,8'd151,8'd93}; v_exp[12]=8'd255;
        // vec 13: [19,225,175,47,1,64,159,62,208] -> 255
        v_win[13] = {8'd208,8'd62,8'd159,8'd64,8'd1,8'd47,8'd175,8'd225,8'd19}; v_exp[13]=8'd255;
        // vec 14: [154,137,39,240,187,18,2,163,171] -> 255
        v_win[14] = {8'd171,8'd163,8'd2,8'd18,8'd187,8'd240,8'd39,8'd137,8'd154}; v_exp[14]=8'd255;
        // vec 15: rst_n=0, start=0 -> 0, done=0
        v_win[15] = {72'd0}; v_exp[15]=8'd0;

        errors = 0;
        rst_n = 1;
        @(negedge clk);

        for (i = 0; i < 16; i = i + 1) begin
            rst_n = v_rst_n[i];
            start = v_start[i];
            win = v_win[i];
            #1;
            if (sobel_out !== v_exp[i] || done !== v_exp_done[i]) begin
                $display("vec %0d: in(win=...,start=%b,rst_n=%b) expected(sobel_out=%0d,done=%b) actual(sobel_out=%0d,done=%b)",
                    i, v_start[i], v_rst_n[i], v_exp[i], v_exp_done[i], sobel_out, done);
                errors = errors + 1;
            end else begin
                $display("vec %0d: in(win=...,start=%b,rst_n=%b) expected(sobel_out=%0d,done=%b) actual(sobel_out=%0d,done=%b) OK",
                    i, v_start[i], v_rst_n[i], v_exp[i], v_exp_done[i], sobel_out, done);
            end
            @(negedge clk);
        end

        if (errors == 0)
            $display("cgra_3x3 TEST PASSED");
        else begin
            $display("cgra_3x3 TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule