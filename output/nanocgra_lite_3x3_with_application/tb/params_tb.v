// tb/params_tb.v — unit testbench for params module.
// Verifies that the RTL parameter module matches golden/model/params.py.
// The params module has no ports; we instantiate it and check its localparams
// via hierarchical references.
`include "params.vh"

`timescale 1ns/1ps

module params_tb;

    // Instantiate the parameter module
    params u_params();

    integer errors;

    initial begin
        errors = 0;

        // ---- Clock / UART parameters ----
        if (u_params.CLK_FREQ !== 32'd50_000_000) begin
            $display("vec 0: CLK_FREQ expected=50000000 actual=%0d", u_params.CLK_FREQ);
            errors = errors + 1;
        end
        if (u_params.BAUD_RATE !== 32'd115_200) begin
            $display("vec 1: BAUD_RATE expected=115200 actual=%0d", u_params.BAUD_RATE);
            errors = errors + 1;
        end
        if (u_params.DATA_W !== 8) begin
            $display("vec 2: DATA_W expected=8 actual=%0d", u_params.DATA_W);
            errors = errors + 1;
        end

        // ---- Image geometry ----
        if (u_params.IMG_W !== 32) begin
            $display("vec 3: IMG_W expected=32 actual=%0d", u_params.IMG_W);
            errors = errors + 1;
        end
        if (u_params.IMG_H !== 32) begin
            $display("vec 4: IMG_H expected=32 actual=%0d", u_params.IMG_H);
            errors = errors + 1;
        end
        if (u_params.OUT_W !== 30) begin
            $display("vec 5: OUT_W expected=30 actual=%0d", u_params.OUT_W);
            errors = errors + 1;
        end
        if (u_params.OUT_H !== 30) begin
            $display("vec 6: OUT_H expected=30 actual=%0d", u_params.OUT_H);
            errors = errors + 1;
        end
        if (u_params.LINE_BUF_W !== 32) begin
            $display("vec 7: LINE_BUF_W expected=32 actual=%0d", u_params.LINE_BUF_W);
            errors = errors + 1;
        end

        // ---- MMIO address map ----
        if (u_params.ADDR_SRAM_BASE !== 8'h00) begin
            $display("vec 8: ADDR_SRAM_BASE expected=0 actual=%0d", u_params.ADDR_SRAM_BASE);
            errors = errors + 1;
        end
        if (u_params.ADDR_UART_TXDATA !== 8'h80) begin
            $display("vec 9: ADDR_UART_TXDATA expected=128 actual=%0d", u_params.ADDR_UART_TXDATA);
            errors = errors + 1;
        end
        if (u_params.ADDR_UART_RXDATA !== 8'h81) begin
            $display("vec 10: ADDR_UART_RXDATA expected=129 actual=%0d", u_params.ADDR_UART_RXDATA);
            errors = errors + 1;
        end
        if (u_params.ADDR_UART_STATUS !== 8'h82) begin
            $display("vec 11: ADDR_UART_STATUS expected=130 actual=%0d", u_params.ADDR_UART_STATUS);
            errors = errors + 1;
        end
        if (u_params.ADDR_UART_CTRL !== 8'h83) begin
            $display("vec 12: ADDR_UART_CTRL expected=131 actual=%0d", u_params.ADDR_UART_CTRL);
            errors = errors + 1;
        end
        if (u_params.ADDR_CGRA_CFG_BASE !== 8'h90) begin
            $display("vec 13: ADDR_CGRA_CFG_BASE expected=144 actual=%0d", u_params.ADDR_CGRA_CFG_BASE);
            errors = errors + 1;
        end
        if (u_params.ADDR_CGRA_OPA !== 8'h99) begin
            $display("vec 14: ADDR_CGRA_OPA expected=153 actual=%0d", u_params.ADDR_CGRA_OPA);
            errors = errors + 1;
        end
        if (u_params.ADDR_CGRA_OPB !== 8'h9A) begin
            $display("vec 15: ADDR_CGRA_OPB expected=154 actual=%0d", u_params.ADDR_CGRA_OPB);
            errors = errors + 1;
        end
        if (u_params.ADDR_CGRA_RES !== 8'h9B) begin
            $display("vec 16: ADDR_CGRA_RES expected=155 actual=%0d", u_params.ADDR_CGRA_RES);
            errors = errors + 1;
        end
        if (u_params.ADDR_START !== 8'hA0) begin
            $display("vec 17: ADDR_START expected=160 actual=%0d", u_params.ADDR_START);
            errors = errors + 1;
        end
        if (u_params.ADDR_STATUS !== 8'hA1) begin
            $display("vec 18: ADDR_STATUS expected=161 actual=%0d", u_params.ADDR_STATUS);
            errors = errors + 1;
        end

        // ---- Sobel kernel weights (Gx) ----
        if (u_params.SOBEL_GX_P0 !== -4'sd1) begin
            $display("vec 19: SOBEL_GX_P0 expected=-1 actual=%0d", u_params.SOBEL_GX_P0);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P1 !== 4'sd0) begin
            $display("vec 20: SOBEL_GX_P1 expected=0 actual=%0d", u_params.SOBEL_GX_P1);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P2 !== 4'sd1) begin
            $display("vec 21: SOBEL_GX_P2 expected=1 actual=%0d", u_params.SOBEL_GX_P2);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P3 !== -4'sd2) begin
            $display("vec 22: SOBEL_GX_P3 expected=-2 actual=%0d", u_params.SOBEL_GX_P3);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P4 !== 4'sd0) begin
            $display("vec 23: SOBEL_GX_P4 expected=0 actual=%0d", u_params.SOBEL_GX_P4);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P5 !== 4'sd2) begin
            $display("vec 24: SOBEL_GX_P5 expected=2 actual=%0d", u_params.SOBEL_GX_P5);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P6 !== -4'sd1) begin
            $display("vec 25: SOBEL_GX_P6 expected=-1 actual=%0d", u_params.SOBEL_GX_P6);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P7 !== 4'sd0) begin
            $display("vec 26: SOBEL_GX_P7 expected=0 actual=%0d", u_params.SOBEL_GX_P7);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GX_P8 !== 4'sd1) begin
            $display("vec 27: SOBEL_GX_P8 expected=1 actual=%0d", u_params.SOBEL_GX_P8);
            errors = errors + 1;
        end

        // ---- Sobel kernel weights (Gy) ----
        if (u_params.SOBEL_GY_P0 !== -4'sd1) begin
            $display("vec 28: SOBEL_GY_P0 expected=-1 actual=%0d", u_params.SOBEL_GY_P0);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P1 !== -4'sd2) begin
            $display("vec 29: SOBEL_GY_P1 expected=-2 actual=%0d", u_params.SOBEL_GY_P1);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P2 !== -4'sd1) begin
            $display("vec 30: SOBEL_GY_P2 expected=-1 actual=%0d", u_params.SOBEL_GY_P2);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P3 !== 4'sd0) begin
            $display("vec 31: SOBEL_GY_P3 expected=0 actual=%0d", u_params.SOBEL_GY_P3);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P4 !== 4'sd0) begin
            $display("vec 32: SOBEL_GY_P4 expected=0 actual=%0d", u_params.SOBEL_GY_P4);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P5 !== 4'sd0) begin
            $display("vec 33: SOBEL_GY_P5 expected=0 actual=%0d", u_params.SOBEL_GY_P5);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P6 !== 4'sd1) begin
            $display("vec 34: SOBEL_GY_P6 expected=1 actual=%0d", u_params.SOBEL_GY_P6);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P7 !== 4'sd2) begin
            $display("vec 35: SOBEL_GY_P7 expected=2 actual=%0d", u_params.SOBEL_GY_P7);
            errors = errors + 1;
        end
        if (u_params.SOBEL_GY_P8 !== 4'sd1) begin
            $display("vec 36: SOBEL_GY_P8 expected=1 actual=%0d", u_params.SOBEL_GY_P8);
            errors = errors + 1;
        end

        // ---- Derived bit widths ----
        if (u_params.SOBEL_SUM_W !== 9) begin
            $display("vec 37: SOBEL_SUM_W expected=9 actual=%0d", u_params.SOBEL_SUM_W);
            errors = errors + 1;
        end

        // ---- CGRA grid ----
        if (u_params.CGRA_ROWS !== 3) begin
            $display("vec 38: CGRA_ROWS expected=3 actual=%0d", u_params.CGRA_ROWS);
            errors = errors + 1;
        end
        if (u_params.CGRA_COLS !== 3) begin
            $display("vec 39: CGRA_COLS expected=3 actual=%0d", u_params.CGRA_COLS);
            errors = errors + 1;
        end
        if (u_params.CGRA_NPE !== 9) begin
            $display("vec 40: CGRA_NPE expected=9 actual=%0d", u_params.CGRA_NPE);
            errors = errors + 1;
        end

        // ---- SRAM ----
        if (u_params.SRAM_DEPTH !== 32) begin
            $display("vec 41: SRAM_DEPTH expected=32 actual=%0d", u_params.SRAM_DEPTH);
            errors = errors + 1;
        end

        // ---- Macro-defined parameters (from params.vh) ----
        if (`CLK_FREQ !== 32'd50_000_000) begin
            $display("vec 42: `CLK_FREQ expected=50000000 actual=%0d", `CLK_FREQ);
            errors = errors + 1;
        end
        if (`BAUD_RATE !== 32'd115_200) begin
            $display("vec 43: `BAUD_RATE expected=115200 actual=%0d", `BAUD_RATE);
            errors = errors + 1;
        end
        if (`DATA_W !== 8) begin
            $display("vec 44: `DATA_W expected=8 actual=%0d", `DATA_W);
            errors = errors + 1;
        end
        if (`IMG_W !== 32) begin
            $display("vec 45: `IMG_W expected=32 actual=%0d", `IMG_W);
            errors = errors + 1;
        end
        if (`IMG_H !== 32) begin
            $display("vec 46: `IMG_H expected=32 actual=%0d", `IMG_H);
            errors = errors + 1;
        end
        if (`OUT_W !== 30) begin
            $display("vec 47: `OUT_W expected=30 actual=%0d", `OUT_W);
            errors = errors + 1;
        end
        if (`OUT_H !== 30) begin
            $display("vec 48: `OUT_H expected=30 actual=%0d", `OUT_H);
            errors = errors + 1;
        end
        if (`BAUD_DIV !== 32'd434) begin
            $display("vec 49: `BAUD_DIV expected=434 actual=%0d", `BAUD_DIV);
            errors = errors + 1;
        end

        // ---- Sobel compute verification using params ----
        // Verify that the Sobel kernel weights produce correct results
        // for known test windows (from golden/model/sobel_core.py)
        // Gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
        // Gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
        // out = min(|Gx| + |Gy|, 255)

        // Test 1: uniform window -> 0
        // Test 2: vertical edge -> 255
        // Test 3: ramp -> 80
        // These are verified in sobel_core_tb; here we just check the params.

        if (errors == 0)
            $display("params TEST PASSED");
        else begin
            $display("params TEST FAILED: %0d errors", errors);
            $fatal(1);
        end
        $finish;
    end

endmodule