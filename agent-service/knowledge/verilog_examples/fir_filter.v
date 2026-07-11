/*
 * Copyright (c) 2023, Your Name <your.email@example.com>
 * All rights reserved.
 *
 * This source code is licensed under the BSD-style license found in the
 * LICENSE file in the root directory of this source tree.
 */

// A generic, parameterizable, fully parallel FIR filter.
module fir_filter #(
    // Data and Coefficient Widths
    parameter IWIDTH    = 16,
    parameter OWIDTH    = 16,
    parameter COEFWIDTH = 16,
    // Number of filter taps
    parameter NTAPS     = 11
) (
    // Clock and Reset
    input wire          clk,
    input wire          arst,

    // Input Data Interface
    input wire          input_valid,
    input wire signed   [IWIDTH-1:0] din,

    // Output Data Interface
    output wire         output_valid,
    output wire signed  [OWIDTH-1:0] dout
);

    //================================================================
    // Parameters
    //================================================================

    // Internal accumulator width. Should be large enough to prevent overflow.
    // A safe value is IWIDTH + COEFWIDTH + $clog2(NTAPS).
    localparam ACCUM_WIDTH = IWIDTH + COEFWIDTH + $clog2(NTAPS);

    // Pipeline stages for latency calculation
    // 1 for input register, 1 for multiplier, ceil($clog2(NTAPS)) for adder tree
    localparam PIPELINE_STAGES = 1 + 1 + $clog2(NTAPS);

    //================================================================
    // Coefficients
    //================================================================
    // Example 11-tap low-pass filter coefficients (scaled and rounded)
    // Symmetric coefficients allow for some hardware optimization, but a
    // generic direct-form structure is implemented here for clarity.
    localparam signed [COEFWIDTH-1:0] COEFF_0 = 16'd26;
    localparam signed [COEFWIDTH-1:0] COEFF_1 = 16'd83;
    localparam signed [COEFWIDTH-1:0] COEFF_2 = 16'd255;
    localparam signed [COEFWIDTH-1:0] COEFF_3 = 16'd563;
    localparam signed [COEFWIDTH-1:0] COEFF_4 = 16'd852;
    localparam signed [COEFWIDTH-1:0] COEFF_5 = 16'd980;
    localparam signed [COEFWIDTH-1:0] COEFF_6 = 16'd852;
    localparam signed [COEFWIDTH-1:0] COEFF_7 = 16'd563;
    localparam signed [COEFWIDTH-1:0] COEFF_8 = 16'd255;
    localparam signed [COEFWIDTH-1:0] COEFF_9 = 16'd83;
    localparam signed [COEFWIDTH-1:0] COEFF_10 = 16'd26;

    //================================================================
    // Internal Signals
    //================================================================
    // Shift register to hold input samples
    reg  signed [IWIDTH-1:0]   shift_reg [0:NTAPS-1];

    // Pipeline registers for multiply-accumulate stages
    reg  signed [ACCUM_WIDTH-1:0] product_regs [0:NTAPS-1];
    reg  signed [ACCUM_WIDTH-1:0] adder_stage1 [0:(NTAPS-1)/2];
    reg  signed [ACCUM_WIDTH-1:0] adder_stage2 [0:((NTAPS-1)/2)/2];
    reg  signed [ACCUM_WIDTH-1:0] adder_stage3 [0:(((NTAPS-1)/2)/2)/2];
    reg  signed [ACCUM_WIDTH-1:0] adder_stage4; // Final accumulator output

    // Pipeline for validity signal
    reg  [PIPELINE_STAGES-1:0] valid_pipeline;

    integer i;

    //================================================================
    // Input Shift Register
    //================================================================
    // On each valid input, shift new data into the register array.
    always @(posedge clk) begin
        if (arst) begin
            for (i = 0; i < NTAPS; i = i + 1) begin
                shift_reg[i] <= 0;
            end
        end else if (input_valid) begin
            shift_reg[0] <= din;
            for (i = 1; i < NTAPS; i = i + 1) begin
                shift_reg[i] <= shift_reg[i-1];
            end
        end
    end

    //================================================================
    // Multiply-Accumulate (MAC) Pipeline
    //================================================================

    // Stage 1: Multiply input samples by coefficients
    always @(posedge clk) begin
        if (arst) begin
            for (i = 0; i < NTAPS; i = i + 1) begin
                product_regs[i] <= 0;
            end
        end else begin
            product_regs[0] <= shift_reg[0] * COEFF_0;
            product_regs[1] <= shift_reg[1] * COEFF_1;
            product_regs[2] <= shift_reg[2] * COEFF_2;
            product_regs[3] <= shift_reg[3] * COEFF_3;
            product_regs[4] <= shift_reg[4] * COEFF_4;
            product_regs[5] <= shift_reg[5] * COEFF_5;
            product_regs[6] <= shift_reg[6] * COEFF_6;
            product_regs[7] <= shift_reg[7] * COEFF_7;
            product_regs[8] <= shift_reg[8] * COEFF_8;
            product_regs[9] <= shift_reg[9] * COEFF_9;
            product_regs[10] <= shift_reg[10] * COEFF_10;
        end
    end

    // Stage 2: Adder Tree - First Level
    always @(posedge clk) begin
        if (arst) begin
            for (i = 0; i <= (NTAPS-1)/2; i = i + 1) begin
                adder_stage1[i] <= 0;
            end
        end else begin
            adder_stage1[0] <= product_regs[0] + product_regs[1];
            adder_stage1[1] <= product_regs[2] + product_regs[3];
            adder_stage1[2] <= product_regs[4] + product_regs[5];
            adder_stage1[3] <= product_regs[6] + product_regs[7];
            adder_stage1[4] <= product_regs[8] + product_regs[9];
            // Pass through the odd tap
            adder_stage1[5] <= product_regs[10];
        end
    end

    // Stage 3: Adder Tree - Second Level
    always @(posedge clk) begin
        if (arst) begin
            for (i = 0; i <= ((NTAPS-1)/2)/2; i = i + 1) begin
                adder_stage2[i] <= 0;
            end
        end else begin
            adder_stage2[0] <= adder_stage1[0] + adder_stage1[1];
            adder_stage2[1] <= adder_stage1[2] + adder_stage1[3];
            // Pass through the odd tap
            adder_stage2[2] <= adder_stage1[4] + adder_stage1[5];
        end
    end

    // Stage 4: Adder Tree - Third Level
    always @(posedge clk) begin
        if (arst) begin
            for (i = 0; i <= (((NTAPS-1)/2)/2)/2; i = i + 1) begin
                adder_stage3[i] <= 0;
            end
        end else begin
            adder_stage3[0] <= adder_stage2[0] + adder_stage2[1];
            // Pass through the odd tap
            adder_stage3[1] <= adder_stage2[2];
        end
    end

    // Stage 5: Adder Tree - Final Sum
    always @(posedge clk) begin
        if (arst) begin
            adder_stage4 <= 0;
        end else begin
            adder_stage4 <= adder_stage3[0] + adder_stage3[1];
        end
    end

    //================================================================
    // Output Logic
    //================================================================

    // Pipeline the input_valid signal to generate a synchronous output_valid
    always @(posedge clk) begin
        if (arst) begin
            valid_pipeline <= 0;
        end else begin
            valid_pipeline <= {valid_pipeline[PIPELINE_STAGES-2:0], input_valid};
        end
    end

    assign output_valid = valid_pipeline[PIPELINE_STAGES-1];

    // Assign the final output, truncating/saturating from the full accumulator width.
    // This example truncates the lower bits and selects the MSBs.
    // For better accuracy, rounding should be implemented.
    assign dout = adder_stage4[ACCUM_WIDTH-1 -: OWIDTH];

endmodule