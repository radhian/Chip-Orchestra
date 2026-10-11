//============================================================================
// pe_tb.v  -  Testbench for the Processing Element datapath.
//   Coverage:
//     * ALU ops: ADD, SUB, AND, OR, XOR, MUL, PASS
//     * MAC clocked-accumulator behaviour
//     * N/S/E/W neighbor-data routing (operand-B source select)
//     * config-register write (cfg_reg selects op + routing)
//   Every check prints expected=.. actual=.. ; global timeout watchdog.
//============================================================================
`timescale 1ns / 1ps
`include "params.vh"

module pe_tb;
    localparam DW = 8;

    reg              clk, rst_n;
    reg              load_cfg, load_data, en;
    reg  [DW-1:0]    cfg_in, data_in;
    reg  [DW-1:0]    src_n, src_s, src_e, src_w;
    wire [DW-1:0]    result;

    integer errors;

    pe #(.DW(DW)) dut (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg_in), .data_in(data_in),
        .src_n(src_n), .src_s(src_s), .src_e(src_e), .src_w(src_w),
        .result(result));

    initial clk = 1'b0;
    always #50 clk = ~clk;

    // Timeout watchdog
    initial begin
        #100000;
        $display("Result: FAILED (timeout)");
        $finish;
    end

    // Configure PE (write config register) + load local operand-A, then eval once.
    // Operand-B is presented on the routing direction chosen by bsel.
    task run(input [2:0] op, input [1:0] bsel,
             input [DW-1:0] a, input [DW-1:0] b,
             input [DW-1:0] exp, input [255:0] name);
        begin
            @(negedge clk);
            // route B onto the selected neighbor, put a decoy on the others
            src_n = 8'hDE; src_s = 8'hAD; src_e = 8'hBE; src_w = 8'hEF;
            case (bsel)
                `SEL_N: src_n = b;
                `SEL_S: src_s = b;
                `SEL_E: src_e = b;
                `SEL_W: src_w = b;
            endcase
            cfg_in    = {3'b0, bsel, op};   // config-register write
            data_in   = a;
            load_cfg  = 1'b1;
            load_data = 1'b1;
            @(negedge clk);                 // cfg_reg<=cfg_in, local_reg<=a, acc cleared
            load_cfg  = 1'b0;
            load_data = 1'b0;
            en = 1'b1;
            @(negedge clk);                 // acc<=result
            en = 1'b0;
            @(negedge clk);
            if (result === exp)
                $display("PASS  %0s  expected=%0d  actual=%0d", name, exp, result);
            else begin
                $display("FAIL  %0s  expected=%0d  actual=%0d", name, exp, result);
                errors = errors + 1;
            end
        end
    endtask

    integer i;
    initial begin
        errors = 0;
        rst_n = 1'b0;
        {load_cfg, load_data, en} = 3'b0;
        {cfg_in, data_in, src_n, src_s, src_e, src_w} = 0;
        repeat (2) @(negedge clk);
        rst_n = 1'b1;

        // ---- ALU operations (operand-B via North) --------------------
        run(`OP_ADD, `SEL_N, 8'd5,  8'd3,  8'd8,   "OP_ADD");
        run(`OP_SUB, `SEL_N, 8'd10, 8'd4,  8'd6,   "OP_SUB");
        run(`OP_AND, `SEL_N, 8'hF0, 8'h3C, 8'h30,  "OP_AND");
        run(`OP_OR,  `SEL_N, 8'hF0, 8'h0F, 8'hFF,  "OP_OR");
        run(`OP_XOR, `SEL_N, 8'hAA, 8'hFF, 8'h55,  "OP_XOR");
        run(`OP_MUL, `SEL_N, 8'd12, 8'd12, 8'd144, "OP_MUL");
        run(`OP_PASS,`SEL_N, 8'd77, 8'd0,  8'd77,  "OP_PASS");

        // ---- N/S/E/W routing: same ADD, operand-B on each direction --
        run(`OP_ADD, `SEL_N, 8'd20, 8'd7, 8'd27, "ROUTE_N");
        run(`OP_ADD, `SEL_S, 8'd20, 8'd8, 8'd28, "ROUTE_S");
        run(`OP_ADD, `SEL_E, 8'd20, 8'd9, 8'd29, "ROUTE_E");
        run(`OP_ADD, `SEL_W, 8'd20, 8'd6, 8'd26, "ROUTE_W");

        // ---- Config-register write proof: reconfigure op then reuse --
        run(`OP_XOR, `SEL_W, 8'h0F, 8'hF0, 8'hFF, "CFG_REWRITE");

        // ---- MAC: accumulate 3*4 four times = 48 ---------------------
        @(negedge clk);
        src_n = 8'd4;
        cfg_in = {3'b0, `SEL_N, `OP_MAC}; load_cfg = 1'b1;
        data_in = 8'd3;                   load_data = 1'b1;
        @(negedge clk);
        load_cfg = 1'b0; load_data = 1'b0;    // acc cleared by load_cfg
        for (i = 0; i < 4; i = i + 1) begin
            en = 1'b1;
            @(negedge clk);
        end
        en = 1'b0;
        @(negedge clk);
        if (result === 8'd48)
            $display("PASS  OP_MAC  expected=%0d  actual=%0d", 8'd48, result);
        else begin
            $display("FAIL  OP_MAC  expected=%0d  actual=%0d", 8'd48, result);
            errors = errors + 1;
        end

        if (errors == 0) $display("Result: PASSED");
        else             $display("Result: FAILED (%0d mismatch)", errors);
        $finish;
    end
endmodule
