module fazyrv_tb;

    // Clock and Reset
    reg clk;
    reg rst_n;
    
    // DUT Signals
    reg [7:0] inst_addr;
    reg [7:0] inst_data;
    wire inst_valid;
    reg [7:0] reg_write_data;
    reg [2:0] reg_write_idx;
    wire [7:0] reg_read_data;
    wire reg_write_en;
    wire [7:0] pc;
    wire pc_valid;
    wire irq;
    wire cpu_busy;
    wire cpu_idle;

    // Instantiate DUT
    // Using a minimal configuration as per RTL comments
    fazyrv dut (
        .clk(clk),
        .rst_n(rst_n),
        .inst_addr(inst_addr),
        .inst_data(inst_data),
        .inst_valid(inst_valid),
        .reg_write_data(reg_write_data),
        .reg_write_idx(reg_write_idx),
        .reg_read_data(reg_read_data),
        .reg_write_en(reg_write_en),
        .pc(pc),
        .pc_valid(pc_valid),
        .irq(irq),
        .cpu_busy(cpu_busy),
        .cpu_idle(cpu_idle)
    );

    // Clock Generation
    initial clk = 0;
    always #5 clk = ~clk;

    // Test Control
    integer cycles;
    integer errors;
    integer timeout_counter;
    reg test_done;
    
    initial begin
        clk = 0;
        rst_n = 0;
        cycles = 0;
        errors = 0;
        timeout_counter = 0;
        test_done = 0;
        
        // Wait for reset to stabilize
        @(posedge clk);
        @(posedge clk);
        
        // Release Reset
        rst_n = 1;
        
        // --- TEST CASES ---
        
        // CASE 1: NOP (Idle)
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00000000; // OP_NOP
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            // Wait for execution
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Check Status
            $display("CASE NOP: in=0x%h expected=0 actual=%0d -> %s", inst_data, cpu_busy, (cpu_busy==0) ? "PASS" : "FAIL");
            errors = errors + (cpu_busy==0 ? 0 : 1);
            
            // Advance PC
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 2: ADD (R + Imm)
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00001100; // OP_ADD (opcode 3, imm 4)
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: 0 + 4 = 4
            $display("CASE ADD: in=0x%h expected=4 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==4) ? "PASS" : "FAIL");
            errors = errors + (reg_read_data==4 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 3: SUB (R - Imm)
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00010004; // OP_SUB (opcode 4, imm 4)
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: 0 - 4 = -4 (Two's complement 252)
            $display("CASE SUB: in=0x%h expected=252 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==252) ? "PASS" : "FAIL");
            errors = errors + (reg_read_data==252 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 4: AND
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00010107; // OP_AND (opcode 5, imm 7)
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: 0 & 7 = 0
            $display("CASE AND: in=0x%h expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
            errors = errors + (reg_read_data==0 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 5: OR
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00011007; // OP_OR (opcode 6, imm 7)
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: 0 | 7 = 7
            $display("CASE OR: in=0x%h expected=7 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==7) ? "PASS" : "FAIL");
            errors = errors + (reg_read_data==7 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 6: XOR
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00011107; // OP_XOR (opcode 7, imm 7)
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: 0 ^ 7 = 7
            $display("CASE XOR: in=0x%h expected=7 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==7) ? "PASS" : "FAIL");
            errors = errors + (reg_read_data==7 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 7: HALT
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00101100; // OP_HALT (opcode 11)
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: CPU Idle
            $display("CASE HALT: in=0x%h expected=0 actual=%0d -> %s", inst_data, cpu_busy, (cpu_busy==0) ? "PASS" : "FAIL");
            errors = errors + (cpu_busy==0 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 8: Boundary - Max Immediate (7)
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00001107; // OP_ADD with max imm
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: 0 + 7 = 7
            $display("CASE MAX_IMM: in=0x%h expected=7 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==7) ? "PASS" : "FAIL");
            errors = errors + (reg_read_data==7 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 9: Boundary - Min Immediate (0)
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00001100; // OP_ADD with imm 0
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 0;
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // Expected: 0 + 0 = 0
            $display("CASE MIN_IMM: in=0x%h expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
            errors = errors + (reg_read_data==0 ? 0 : 1);
            
            @(posedge clk);
            @(posedge clk);
        end
        
        // CASE 10: IRQ Handling
        begin
            inst_addr = 8'd0;
            inst_data = 8'b00000000; // NOP
            reg_write_data = 8'd0;
            reg_write_idx = 3'd0;
            irq = 1; // Trigger IRQ
            
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            @(posedge clk);
            
            // IRQ should invalidate instruction
            $display("CASE IRQ: in=0x%h expected=0 actual=%0d -> %s", inst_data, inst_valid, (inst_valid==0) ? "PASS" : "FAIL");
            errors = errors + (inst_valid==0 ? 0 : 1);
            
            irq = 0; // Clear IRQ
            @(posedge clk);
            @(posedge clk);
        end
        
        // --- END OF TESTS ---
        
        // Print Cycle Count
        $display("CYCLES: total=%0d", cycles);
        
        // Summary
        $display("SUMMARY: %0d checks, %0d failed", 10, errors);
        
        if (errors == 0) begin
            $display("Result: PASSED");
        end else begin
            $display("Result: FAILED");
        end
        
        test_done = 1;
        $finish;
    end

endmodule