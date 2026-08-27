// tb/pe_tb.v — unit testbench for pe.
// Vectors from golden/vectors/pe.json (10 vectors).
`include "params.vh"

`timescale 1ns/1ps

module pe_tb;

    reg clk;
    reg rst_n;
    reg [2:0] cfg;
    reg [7:0] opa;
    reg [7:0] opb;
    wire [7:0] result;
    wire [7:0] cout;

    integer i;
    integer errors;

    // DUT
    pe dut (
        .clk(clk),
        .rst_n(rst_n),
        .cfg(cfg),
        .opa(opa),
        .opb(opb),
        .result(result),
        .cout(cout)
    );

    // Clock
    initial clk = 0;
    always #5 clk = ~clk;

    // Vectors: {rst_n, cfg, opa, opb, exp_result, exp_cout}
    reg [0:9] v_rst_n   = 10'b1111111110;
    reg [2:0] v_cfg  [0:9];
    reg [7:0] v_opa  [0:9];
    reg [7:0] v_opb  [0:9];
    reg [7:0] v_eres [0:9];
    reg [7:0] v_eco  [0:9];

    initial begin
        // vec 0: cfg=0, opa=83, opb=0 -> result=83, cout=83
        v_cfg[0]=3'd0; v_opa[0]=8'd83; v_opb[0]=8'd0; v_eres[0]=8'd83; v_eco[0]=8'd83;
        // vec 1: cfg=6, opa=255, opb=0 -> result=0, cout=0
        v_cfg[1]=3'd6; v_opa[1]=8'd255; v_opb[1]=8'd0; v_eres[1]=8'd0; v_eco[1]=8'd0;
        // vec 2: cfg=3, opa=16, opb=0 -> result=32, cout=32
        v_cfg[2]=3'd3; v_opa[2]=8'd16; v_opb[2]=8'd0; v_eres[2]=8'd32; v_eco[2]=8'd32;
        // vec 3: cfg=3, opa=128, opb=0 -> result=0, cout=0
        v_cfg[3]=3'd3; v_opa[3]=8'd128; v_opb[3]=8'd0; v_eres[3]=8'd0; v_eco[3]=8'd0;
        // vec 4: cfg=4, opa=5, opb=0 -> result=251, cout=251
        v_cfg[4]=3'd4; v_opa[4]=8'd5; v_opb[4]=8'd0; v_eres[4]=8'd251; v_eco[4]=8'd251;
        // vec 5: cfg=5, opa=3, opb=0 -> result=250, cout=250
        v_cfg[5]=3'd5; v_opa[5]=8'd3; v_opb[5]=8'd0; v_eres[5]=8'd250; v_eco[5]=8'd250;
        // vec 6: cfg=7, opa=251, opb=0 -> result=5, cout=5
        v_cfg[6]=3'd7; v_opa[6]=8'd251; v_opb[6]=8'd0; v_eres[6]=8'd5; v_eco[6]=8'd5;
        // vec 7: cfg=1, opa=16, opb=2 -> result=32, cout=32
        v_cfg[7]=3'd1; v_opa[7]=8'd16; v_opb[7]=8'd2; v_eres[7]=8'd32; v_eco[7]=8'd32;
        // vec 8: cfg=2, opa=16, opb=5 -> result=21, cout=21
        v_cfg[8]=3'd2; v_opa[8]=8'd16; v_opb[8]=8'd5; v_eres[8]=8'd21; v_eco[8]=8'd21;
        // vec 9: cfg=0, opa=66, opb=0, rst_n=0 -> result=0, cout=0
        v_cfg[9]=3'd0; v_opa[9]=8'd66; v_opb[9]=8'd0; v_eres[9]=8'd0; v_eco[9]=8'd0;

        errors = 0;
        rst_n = 0;
        cfg = 0; opa = 0; opb = 0;
        @(negedge clk);
        @(negedge clk);

        for (i = 0; i < 10; i = i + 1) begin
            rst_n = v_rst_n[i];
            cfg = v_cfg[i];
            opa = v_opa[i];
            opb = v_opb[i];
            #1;  // combinational settle
            if (result !== v_eres[i] || cout !== v_eco[i]) begin
                $display("vec %0d: in(cfg=%0d,opa=%0d,opb=%0d,rst_n=%b) expected(result=%0d,cout=%0d) actual(result=%0d,cout=%0d)",
                    i, v_cfg[i], v_opa[i], v_opb[i], v_rst_n[i], v_eres[i], v_eco[i], result, cout);
                errors = errors + 1;
            end else begin
                $display("vec %0d: in(cfg=%0d,opa=%0d,opb=%0d,rst_n=%b) expected(result=%0d,cout=%0d) actual(result=%0d,cout=%0d) OK",
                    i, v_cfg[i], v_opa[i], v_opb[i], v_rst_n[i], v_eres[i], v_eco[i], result, cout);
            end
            @(negedge clk);
        end

        if (errors == 0)
            $display("pe TEST PASSED");
        else begin
            $display("pe TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule