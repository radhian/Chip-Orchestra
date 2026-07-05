module FazyRV_Core_tb;

    // Clock
    reg clk;
    
    // Test Control
    reg rst_n;
    reg [7:0] inst_addr;
    reg [7:0] inst_data;
    reg [7:0] reg_write_data;
    reg [2:0] reg_write_idx;
    reg irq;
    reg [7:0] expected_reg_read_data;
    reg expected_reg_write_en;
    reg expected_pc;
    reg expected_pc_valid;
    reg expected_cpu_busy;
    reg expected_cpu_idle;
    reg expected_inst_valid;
    
    // Counters and Errors
    integer cycles;
    integer errors;
    integer check_count;
    integer timeout_counter;
    
    // DUT Instance
    // Using a small override for any potential timing issues, though this DUT is combinational-heavy
    FazyRV_Core dut (
        .clk(clk),
        .rst_n(rst_n),
        .inst_addr(inst_addr),
        .inst_data(inst_data),
        .inst_valid(dut_inst_valid),
        .reg_write_data(reg_write_data),
        .reg_write_idx(reg_write_idx),
        .reg_read_data(dut_reg_read_data),
        .reg_write_en(dut_reg_write_en),
        .pc(dut_pc),
        .pc_valid(dut_pc_valid),
        .irq(irq),
        .cpu_busy(dut_cpu_busy),
        .cpu_idle(dut_cpu_idle)
    );

    // Clock Generation
    always #5 clk = ~clk;

    // Test Sequence
    initial begin
        // Initialize
        clk = 0;
        rst_n = 0;
        cycles = 0;
        errors = 0;
        check_count = 0;
        timeout_counter = 0;
        
        // Wait for reset to release
        @(posedge clk);
        rst_n = 1;
        @(posedge clk);
        
        // --- TEST CASE 1: NOP ---
        // Input: NOP opcode (000000)
        inst_data = 8'b00000000; // NOP
        inst_addr = 8'd0;
        
        // Wait for execution
        @(posedge clk);
        @(posedge clk);
        
        // Check
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd8;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE NOP: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 2: ADD ---
        // Input: ADD opcode (000011), imm=5
        inst_data = 8'b00001105; // ADD, imm=5
        inst_addr = 8'd8;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd16;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE ADD: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 3: AND ---
        // Input: AND opcode (000101), imm=15
        inst_data = 8'b00010115; // AND, imm=15
        inst_addr = 8'd16;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd24;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE AND: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 4: OR ---
        // Input: OR opcode (000110), imm=20
        inst_data = 8'b00011014; // OR, imm=20
        inst_addr = 8'd24;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd32;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE OR: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 5: XOR ---
        // Input: XOR opcode (000111), imm=10
        inst_data = 8'b00011110; // XOR, imm=10
        inst_addr = 8'd32;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd40;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE XOR: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 6: HALT ---
        // Input: HALT opcode (001011)
        inst_data = 8'b00101100; // HALT
        inst_addr = 8'd40;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd0; // HALT resets PC
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE HALT: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 7: LOAD (Immediate) ---
        // Input: LOAD opcode (000001), imm=42
        inst_data = 8'b0000012A; // LOAD, imm=42
        inst_addr = 8'd48;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd56;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE LOAD: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 8: STORE (Immediate) ---
        // Input: STORE opcode (000010), imm=100
        inst_data = 8'b00001064; // STORE, imm=100
        inst_addr = 8'd56;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd64;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE STORE: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 9: SUB ---
        // Input: SUB opcode (000100), imm=5
        inst_data = 8'b00010005; // SUB, imm=5
        inst_addr = 8'd64;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd72;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE SUB: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 10: Boundary - Max Immediate ---
        // Input: ADD with max immediate (63)
        inst_data = 8'b0000113F; // ADD, imm=63
        inst_addr = 8'd72;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd80;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE MAX_IMM: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 11: Boundary - Min Immediate ---
        // Input: ADD with min immediate (0)
        inst_data = 8'b00001100; // ADD, imm=0
        inst_addr = 8'd80;
        
        @(posedge clk);
        @(posedge clk);
        
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd88;
        expected_pc_valid = 1'b1;
        expected_inst_valid = 1'b1;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE MIN_IMM: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // --- TEST CASE 12: IRQ Handling ---
        // Input: NOP, then assert IRQ
        inst_data = 8'b00000000; // NOP
        inst_addr = 8'd88;
        
        @(posedge clk);
        @(posedge clk);
        
        // Assert IRQ
        irq = 1'b1;
        @(posedge clk);
        @(posedge clk);
        
        // IRQ should invalidate instruction
        expected_reg_read_data = 8'd0;
        expected_reg_write_en = 1'b0;
        expected_pc = 8'd0; // IRQ resets state
        expected_pc_valid = 1'b0;
        expected_inst_valid = 1'b0;
        expected_cpu_busy = 1'b0;
        expected_cpu_idle = 1'b1;
        
        $display("CASE IRQ: in=0x%h expected=%0d actual=%0d -> %s", inst_data, expected_pc, dut_pc, (dut_pc === expected_pc) ? "PASS" : "FAIL");
        errors = errors + (dut_pc !== expected_pc ? 1 : 0);
        check_count = check_count + 1;
        
        // Release IRQ
        irq = 1'b0;
        @(posedge clk);
        @(posedge clk);
        
        // --- TIMEOUT WATCHDOG ---
        timeout_counter = 0;
        while (timeout_counter < 2000000) begin
            @(posedge clk);
            timeout_counter = timeout_counter + 1;
        end
        
        // Summary
        $display("CYCLES: total=%0d", cycles);
        $display("SUMMARY: %0d checks, %0d failed", check_count, errors);
        
        if (errors == 0) begin
            $display("Result: PASSED");
        end else begin
            $display("Result: FAILED");
        end
        
        $finish;
    end

endmodule