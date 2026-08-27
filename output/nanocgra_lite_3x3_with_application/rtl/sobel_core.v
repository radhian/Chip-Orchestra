// sobel_core.v — Sobel Gx/Gy shift-add compute + magnitude saturate.
// Pure combinational datapath.
//   Gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
//   Gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
//   out = min(|Gx| + |Gy|, 255)
// Intermediate Gx, Gy signed 11-bit (-510..+510); magnitude 0..1020 saturated to u8.
`include "params.vh"

module sobel_core (
    input  wire [71:0] win,          // 9 x 8-bit, row-major 0=TL..8=BR
    output reg  [`DATA_W-1:0] sobel_out
);

    // unpack window
    wire [7:0] w0 = win[7:0];
    wire [7:0] w1 = win[15:8];
    wire [7:0] w2 = win[23:16];
    wire [7:0] w3 = win[31:24];
    wire [7:0] w4 = win[39:32];
    wire [7:0] w5 = win[47:40];
    wire [7:0] w6 = win[55:48];
    wire [7:0] w7 = win[63:56];
    wire [7:0] w8 = win[71:64];

    // signed extensions (pixels are unsigned 0..255)
    wire signed [10:0] p0 = $signed({3'b0, w0});
    wire signed [10:0] p1 = $signed({3'b0, w1});
    wire signed [10:0] p2 = $signed({3'b0, w2});
    wire signed [10:0] p3 = $signed({3'b0, w3});
    wire signed [10:0] p5 = $signed({3'b0, w5});
    wire signed [10:0] p6 = $signed({3'b0, w6});
    wire signed [10:0] p7 = $signed({3'b0, w7});
    wire signed [10:0] p8 = $signed({3'b0, w8});

    // Gx = -w0 + w2 - 2*w3 + 2*w5 - w6 + w8
    wire signed [10:0] gx = -p0 + p2 - (p3 << 1) + (p5 << 1) - p6 + p8;
    // Gy = -w0 - 2*w1 - w2 + w6 + 2*w7 + w8
    wire signed [10:0] gy = -p0 - (p1 << 1) - p2 + p6 + (p7 << 1) + p8;

    // absolute values
    wire signed [10:0] abs_gx = (gx < 0) ? -gx : gx;
    wire signed [10:0] abs_gy = (gy < 0) ? -gy : gy;

    // magnitude |Gx| + |Gy|  (0..1020)
    wire [10:0] mag = abs_gx + abs_gy;

    // saturate to 0..255
    always @(*) begin
        if (mag > 11'd255)
            sobel_out = 8'd255;
        else
            sobel_out = mag[7:0];
    end

endmodule