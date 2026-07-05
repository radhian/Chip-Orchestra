module fazyrv_tb;

    // Clock
    reg clk;
    
    // Reset
    reg rst_n;
    
    // DUT Inputs
    reg [7:0] inst_addr;
    reg [7:0] inst_data;
    reg reg_write_data;
    reg [2:0] reg_write_idx;
    reg irq;
    
    // DUT Outputs
    wire inst_valid;
    wire [7:0] reg_read_data;
    wire reg_write_en;
    wire [7:0] pc;
    wire pc_valid;
    wire cpu_busy;
    wire cpu_idle;
    
    // DUT Instance
    // Using a small parameter override for any potential timing issues, though this RTL is combinational/state based.
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

    // Test Control & Counters
    integer cycles;
    integer errors;
    integer check_count;
    integer timeout_cycles;
    
    // Timeout watchdog
    initial begin
        timeout_cycles = 2000000;
        #timeout_cycles $display("Result: FAILED (timeout)");
        $finish;
    end

    // Test Sequences
    // Helper to wait for a state or signal
    task wait_for_idle;
        begin
            @(posedge clk);
            while (cpu_busy) @(posedge clk);
        end
    endtask

    // Helper to wait for valid output
    task wait_for_valid;
        begin
            @(posedge clk);
            while (!inst_valid) @(posedge clk);
        end
    endtask

    // Test 1: NOP Operation
    initial begin
        rst_n = 0;
        @(posedge clk);
        rst_n = 1;
        @(posedge clk);
        
        // Fetch NOP: [7:6]=00, [5:0]=000000
        inst_addr = 0;
        inst_data = 6'b00_000000;
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        // Check NOP result
        $display("CASE NOP: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 2: ADD Operation
    initial begin
        // Setup registers (simulated by writing to reg_write_data before read)
        // Since RTL reads regfile[rs-1], we must ensure regfile is initialized or we test immediate ops.
        // This RTL reads from regfile. Let's assume regfile is pre-loaded or we test immediate logic.
        // To make this test robust without external regfile init, we will test immediate arithmetic if possible,
        // but the RTL reads regfile[rs-1]. We will assume regfile[0] is 0 for simplicity in this isolated test.
        
        // Fetch ADD: [7:6]=000011, [5:3]=000 (reg 0), [2:0]=000 (imm 0)
        // Note: RTL uses imm for ADD. Let's set imm=5.
        inst_addr = 0;
        inst_data = 6'b00_001100; // Opcode ADD, rs=0, rt=0, imm=0
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        // Check ADD result (0 + 0)
        $display("CASE ADD: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 3: LOAD Operation (Simulated)
    initial begin
        // Fetch LOAD: [7:6]=000001
        inst_addr = 0;
        inst_data = 6'b00_000100; // Opcode LOAD
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        // Check LOAD result
        $display("CASE LOAD: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 4: HALT Operation
    initial begin
        // Fetch HALT: [7:6]=001011
        inst_addr = 0;
        inst_data = 6'b00_101100; // Opcode HALT
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        // Check HALT result
        $display("CASE HALT: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 5: AND Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_010100; // Opcode AND
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE AND: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 6: OR Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_011000; // Opcode OR
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE OR: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 7: XOR Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_011100; // Opcode XOR
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE XOR: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 8: SUB Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_010000; // Opcode SUB
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE SUB: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 9: STORE Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_001000; // Opcode STORE
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE STORE: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 10: JMP Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_100000; // Opcode JMP
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE JMP: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 11: BNE Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_100100; // Opcode BNE
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE BNE: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 12: BEQ Operation
    initial begin
        inst_addr = 0;
        inst_data = 6'b00_101000; // Opcode BEQ
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        $display("CASE BEQ: in=inst_data=%0d expected=0 actual=%0d -> %s", inst_data, reg_read_data, (reg_read_data==0) ? "PASS" : "FAIL");
        errors = errors + (reg_read_data==0 ? 0 : 1);
        check_count = check_count + 1;
        
        wait_for_idle;
    end

    // Test 13: IRQ Handling (Interrupt)
    initial begin
        rst_n = 1;
        @(posedge clk);
        
        // Fetch NOP
        inst_addr = 0;
        inst_data = 6'b00_000000;
        
        @(posedge clk);
        @(posedge clk);
        @(posedge clk);
        
        // Assert IRQ
        irq = 1;
        
        @(posedge clk);
        @(posedge clk);
        
        // Check that instruction is stalled or reset (inst_valid should be 0 or data cleared)
        // Based on RTL: if (irq) inst_valid <= 0; inst_buffer <= 0;
        $display("CASE IRQ: in=irq=1 expected=0 actual=%0d -> %s", inst_buffer, inst_valid, (inst_valid==0) ? "PASS" : "FAIL");
        errors = errors + (inst_valid==0 ? 0 : 1);
        check_count = check_count + 1;
        
        irq = 0;
        wait_for_idle;
    end

    // Summary
    always @(posedge clk) begin
        if (check_count > 0) begin
            $display("CYCLES: total=%0d", cycles);
            $display("SUMMARY: %0d checks, %0d failed", check_count, errors);
            if (errors == 0) begin
                $display("Result: PASSED");
            end else begin
                $display("Result: FAILED");
            end
            $finish;
        end
    end

endmodule