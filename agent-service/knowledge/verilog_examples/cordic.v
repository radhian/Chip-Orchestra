/*
 * Copyright (c) 2023, Your Company. All rights reserved.
 *
 * This Verilog module implements a fully pipelined CORDIC (COordinate Rotation DIgital Computer)
 * algorithm. It is highly parameterized for data width, number of stages, and operational mode.
 * The CORDIC algorithm is an iterative method for calculating trigonometric functions and vector
 * rotations, using only shifts and additions.
 *
 * The module supports two primary modes:
 * 1. Rotation Mode (MODE = 1): Rotates an input vector (xi, yi) by a given angle (zi).
 *    The outputs are the new coordinates (xo, yo).
 *    - xi' = xi * cos(zi) - yi * sin(zi)
 *    - yi' = yi * cos(zi) + xi * sin(zi)
 *    - zo -> 0
 *
 * 2. Vectoring Mode (MODE = 0): Rotates an input vector (xi, yi) to the x-axis.
 *    The outputs are the vector's magnitude (xo) and its original angle (zo).
 *    - xo -> sqrt(xi^2 + yi^2)
 *    - yo -> 0
 *    - zo -> atan(yi/xi)
 *
 * The pipeline structure allows for high-throughput processing, with a new computation
 * starting on every clock cycle after the initial pipeline latency.
 *
 * This implementation is inspired by common CORDIC architectures seen in signal processing
 * and communications systems.
 */

module cordic #(
    // Parameters to configure the CORDIC core
    parameter DATA_WIDTH = 16,      // Bit width for x, y, and z data paths
    parameter STAGES     = 16,      // Number of CORDIC iterations/pipeline stages. Should ideally be >= DATA_WIDTH.
    parameter MODE       = 1        // 1 for Rotation, 0 for Vectoring
) (
    // System Inputs
    input wire                  clk,    // System clock
    input wire                  reset,  // Synchronous active-high reset
    input wire                  enable, // Pipeline enable

    // Data Inputs
    input wire signed [DATA_WIDTH-1:0] xi,     // Initial X-coordinate
    input wire signed [DATA_WIDTH-1:0] yi,     // Initial Y-coordinate
    input wire signed [DATA_WIDTH-1:0] zi,     // Initial Angle (in radians, scaled)

    // Data Outputs
    output wire signed [DATA_WIDTH-1:0] xo,    // Final X-coordinate / Magnitude
    output wire signed [DATA_WIDTH-1:0] yo,    // Final Y-coordinate
    output wire signed [DATA_WIDTH-1:0] zo     // Final Angle
);

    // Internal pipeline registers for x, y, and z values
    // Array size is STAGES+1 to hold initial inputs and output of each stage
    reg signed [DATA_WIDTH-1:0] x_pipe [0:STAGES];
    reg signed [DATA_WIDTH-1:0] y_pipe [0:STAGES];
    reg signed [DATA_WIDTH-1:0] z_pipe [0:STAGES];

    // Angle Look-Up Table (LUT) for pre-computed atan(2^-i) values.
    // These values are scaled to match the fixed-point representation of 'z'.
    // For example, with DATA_WIDTH=16, angles are often represented as Q2.14,
    // so atan(1) = pi/4 is approx 0.785398, which is 0.785398 * 2^14 = 12867 = 16'h3243.
    function [DATA_WIDTH-1:0] atan_lut;
        input [31:0] i;
        case (i)
            0: atan_lut = 16'h3243; // atan(2^0) * 2^14
            1: atan_lut = 16'h1DAC; // atan(2^-1) * 2^14
            2: atan_lut = 16'h0FAD; // atan(2^-2) * 2^14
            3: atan_lut = 16'h07F5; // atan(2^-3) * 2^14
            4: atan_lut = 16'h03FE; // atan(2^-4) * 2^14
            5: atan_lut = 16'h01FF; // atan(2^-5) * 2^14
            6: atan_lut = 16'h00FF; // atan(2^-6) * 2^14
            7: atan_lut = 16'h007F; // atan(2^-7) * 2^14
            8: atan_lut = 16'h003F; // atan(2^-8) * 2^14
            9: atan_lut = 16'h001F; // atan(2^-9) * 2^14
            10: atan_lut = 16'h000F; // atan(2^-10) * 2^14
            11: atan_lut = 16'h0007; // atan(2^-11) * 2^14
            12: atan_lut = 16'h0003; // atan(2^-12) * 2^14
            13: atan_lut = 16'h0001; // atan(2^-13) * 2^14
            14: atan_lut = 16'h0000; // atan(2^-14) * 2^14
            15: atan_lut = 16'h0000; // atan(2^-15) * 2^14
            default: atan_lut = 0;
        endcase
    endfunction

    // First pipeline stage: Latch the inputs
    // The CORDIC gain is not compensated here but should be handled externally
    // if true magnitude is required. The gain approaches ~1.647.
    // A common practice is to pre-scale the inputs by 1/1.647 (~0.607).
    always @(posedge clk) begin
        if (reset) begin
            x_pipe[0] <= 0;
            y_pipe[0] <= 0;
            z_pipe[0] <= 0;
        end else if (enable) begin
            x_pipe[0] <= xi;
            y_pipe[0] <= yi;
            z_pipe[0] <= zi;
        end
    end

    // Generate the pipeline stages for the CORDIC iterations
    genvar i;
    generate
        for (i = 0; i < STAGES; i = i + 1) begin : cordic_pipeline_stage
            
            // Wires for shifted versions of x and y for the current stage
            wire signed [DATA_WIDTH-1:0] x_shifted;
            wire signed [DATA_WIDTH-1:0] y_shifted;
            
            // The direction of rotation 'd' depends on the mode
            // Rotation Mode: Reduce z to zero. d = sign(z)
            // Vectoring Mode: Reduce y to zero. d = -sign(y)
            wire d = (MODE == 1) ? (z_pipe[i] < 0) : (y_pipe[i] > 0);

            // Perform arithmetic right shifts. The shift amount is the stage index 'i'.
            assign x_shifted = x_pipe[i] >>> i;
            assign y_shifted = y_pipe[i] >>> i;

            // The core CORDIC iteration logic for stage i+1
            always @(posedge clk) begin
                if (reset) begin
                    x_pipe[i+1] <= 0;
                    y_pipe[i+1] <= 0;
                    z_pipe[i+1] <= 0;
                end else if (enable) begin
                    if (d) begin // d=1, corresponds to a negative rotation
                        x_pipe[i+1] <= x_pipe[i] + y_shifted;
                        y_pipe[i+1] <= y_pipe[i] - x_shifted;
                        z_pipe[i+1] <= z_pipe[i] + atan_lut(i);
                    end else begin // d=0, corresponds to a positive rotation
                        x_pipe[i+1] <= x_pipe[i] - y_shifted;
                        y_pipe[i+1] <= y_pipe[i] + x_shifted;
                        z_pipe[i+1] <= z_pipe[i] - atan_lut(i);
                    end
                end
            end
        end
    endgenerate

    // Assign the final pipeline stage outputs to the module outputs
    assign xo = x_pipe[STAGES];
    assign yo = y_pipe[STAGES];
    assign zo = z_pipe[STAGES];

endmodule