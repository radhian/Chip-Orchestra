/*
 * Module: pwm_generator
 *
 * Description:
 * This module generates a Pulse Width Modulated (PWM) signal. The frequency and
 * duty cycle of the PWM signal can be configured dynamically. The core of the
 * module is a counter that increments on each clock cycle. The PWM output is
 * determined by comparing the counter's value against a 'compare' value (for
 * duty cycle) and a 'period' value (for frequency).
 *
 * The PWM frequency is determined by: F_pwm = F_clk / (period + 1)
 * The Duty Cycle is determined by: Duty = compare / (period + 1)
 *
 * For example, with a 100MHz clock:
 * - To get a ~1kHz PWM signal, 'period' should be (100e6 / 1e3) - 1 = 99999.
 * - For a 25% duty cycle, 'compare' should be 99999 * 0.25 = 25000.
 *
 * The rising edge of the PWM output is aligned with the counter reset.
 */
module pwm_generator #(
    parameter COUNTER_WIDTH = 16
) (
    // System Inputs
    input wire clk,
    input wire rst,

    // Configuration Inputs
    input wire [COUNTER_WIDTH-1:0] period,  // The counter will cycle from 0 to this value
    input wire [COUNTER_WIDTH-1:0] compare, // The output is high while counter < compare

    // Output
    output reg pwm_out                      // The PWM output signal
);

    // Internal counter
    reg [COUNTER_WIDTH-1:0] counter_reg;

    // Main sequential logic block
    always @(posedge clk) begin
        if (rst) begin
            // Reset state
            counter_reg <= 0;
            pwm_out     <= 1'b0;
        end else begin
            // Counter logic: increments up to 'period' and then resets to 0
            if (counter_reg >= period) begin
                counter_reg <= 0;
            end else begin
                counter_reg <= counter_reg + 1;
            end

            // PWM generation logic: output is high when counter is less than the compare value
            if (counter_reg < compare) begin
                pwm_out <= 1'b1;
            end else begin
                pwm_out <= 1'b0;
            end
        end
    end

endmodule
