//============================================================================
// nano_controller_tb.v  -  Testbench for the FSM-only Nano Controller.
//   Coverage:
//     * State transitions IDLE -> RD_A -> RD_B -> LOAD(CONFIG) -> EXEC -> STORE -> DONE
//     * SRAM read path  (operand-A / operand-B captured from the shared port)
//     * SRAM write path (CGRA result committed to res_addr)
//   A behavioural SRAM model (1-cycle registered read) and a stand-in ALU
//   (cgra_result = data_a + data_b) drive the DUT.
//   Every check prints expected=.. actual=.. ; global timeout watchdog.
//   Note: the UART is a memory-mapped peripheral, NOT wired into the
//   controller datapath; its receive path is verified in uart_tb.v and the
//   end-to-end UART chain in nanocgra_lite_tb.v.
//============================================================================
`timescale 1ns / 1ps
`include "params.vh"

module nano_controller_tb;
    localparam DW = 8, AW = 5;

    reg              clk, rst_n;
    reg              start_pulse;
    reg  [AW-1:0]    opa_addr, opb_addr, res_addr;
    wire [DW-1:0]    sram_rdata;
    wire [DW-1:0]    cgra_result;

    wire             cgra_load_cfg, cgra_load_data, cgra_en;
    wire [DW-1:0]    data_a, data_b;
    wire             m_sram_we;
    wire [AW-1:0]    m_sram_addr;
    wire [DW-1:0]    m_sram_din;
    wire             busy, done;

    integer errors;

    nano_controller #(.DW(DW), .AW(AW)) dut (
        .clk(clk), .rst_n(rst_n),
        .start_pulse(start_pulse),
        .opa_addr(opa_addr), .opb_addr(opb_addr), .res_addr(res_addr),
        .sram_rdata(sram_rdata), .cgra_result(cgra_result),
        .cgra_load_cfg(cgra_load_cfg), .cgra_load_data(cgra_load_data),
        .cgra_en(cgra_en), .data_a(data_a), .data_b(data_b),
        .m_sram_we(m_sram_we), .m_sram_addr(m_sram_addr), .m_sram_din(m_sram_din),
        .busy(busy), .done(done));

    // ---- Behavioural SRAM model (1-cycle registered read) ------------
    reg [DW-1:0] mem [0:31];
    reg [DW-1:0] rdata_r;
    always @(posedge clk) begin
        if (m_sram_we) mem[m_sram_addr] <= m_sram_din;
        rdata_r <= mem[m_sram_addr];
    end
    assign sram_rdata = rdata_r;

    // ---- Stand-in CGRA ALU: result = data_a + data_b -----------------
    assign cgra_result = data_a + data_b;

    initial clk = 1'b0;
    always #50 clk = ~clk;

    initial begin
        #100000;
        $display("Result: FAILED (timeout)");
        $finish;
    end

    // capture the observed state sequence
    reg [2:0] seq [0:15];
    integer   nseq;
    always @(posedge clk) begin
        if (busy || dut.state != `ST_IDLE) begin
            if (nseq < 16) begin
                seq[nseq] = dut.state;
                nseq = nseq + 1;
            end
        end
    end

    task chk(input [255:0] name, input [31:0] exp, input [31:0] act);
        begin
            if (exp === act)
                $display("PASS  %0s  expected=%0d  actual=%0d", name, exp, act);
            else begin
                $display("FAIL  %0s  expected=%0d  actual=%0d", name, exp, act);
                errors = errors + 1;
            end
        end
    endtask

    integer i;
    initial begin
        errors = 0;
        nseq = 0;
        start_pulse = 1'b0;
        opa_addr = 5'd0; opb_addr = 5'd1; res_addr = 5'h10;
        rst_n = 1'b0;
        for (i = 0; i < 32; i = i + 1) mem[i] = 8'd0;
        mem[0] = 8'd5;   // operand A
        mem[1] = 8'd3;   // operand B
        repeat (2) @(negedge clk);
        rst_n = 1'b1;

        // idle before start
        @(negedge clk);
        chk("STATE_IDLE_before_start", `ST_IDLE, dut.state);
        chk("busy_idle", 1'b0, busy);

        // pulse START for one cycle
        @(negedge clk); start_pulse = 1'b1;
        @(negedge clk); start_pulse = 1'b0;

        // walk the FSM and observe transitions
        chk("STATE_RD_A",  `ST_RD_A,  dut.state); @(negedge clk);
        chk("STATE_RD_B",  `ST_RD_B,  dut.state); @(negedge clk);
        chk("STATE_LOAD",  `ST_LOAD,  dut.state);
        chk("busy_during_run", 1'b1, busy);
        chk("cgra_load_cfg_in_LOAD",  1'b1, cgra_load_cfg);
        chk("cgra_load_data_in_LOAD", 1'b1, cgra_load_data);
        @(negedge clk);
        chk("STATE_EXEC",  `ST_EXEC,  dut.state);
        chk("cgra_en_in_EXEC", 1'b1, cgra_en);
        @(negedge clk);
        chk("STATE_STORE", `ST_STORE, dut.state);
        chk("m_sram_we_in_STORE", 1'b1, m_sram_we);
        chk("res_addr_driven", res_addr, m_sram_addr);
        @(negedge clk);
        chk("STATE_DONE",  `ST_DONE,  dut.state);
        chk("done_flag", 1'b1, done);
        @(negedge clk);
        chk("STATE_IDLE_after", `ST_IDLE, dut.state);

        // operand capture from SRAM read path
        chk("SRAM_read_operand_A", 8'd5, data_a);
        chk("SRAM_read_operand_B", 8'd3, data_b);

        // result committed to SRAM (5 + 3 = 8)
        chk("SRAM_write_result", 8'd8, mem[5'h10]);

        if (errors == 0) $display("Result: PASSED");
        else             $display("Result: FAILED (%0d mismatch)", errors);
        $finish;
    end
endmodule
