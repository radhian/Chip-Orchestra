`timescale 1ns/1ps
module fulladder_tb;
    reg a, b, cin;
    wire sum, cout;
    integer i;
    fulladder dut(.a(a), .b(b), .cin(cin), .sum(sum), .cout(cout));
    initial begin
        for (i=0; i<8; i=i+1) begin
            {a,b,cin}=i; #10;
            if ({cout,sum} !== ({1'b0,a}+{1'b0,b}+{1'b0,cin}))
                $fatal(1,"Full adder mismatch vector %0d observed=%b expected=%b",i,{cout,sum},({1'b0,a}+{1'b0,b}+{1'b0,cin}));
        end
        $display("TEST PASSED fulladder checks=8");
        $finish;
    end
endmodule
