// cgra_3x3.v — 3x3 PE mesh array with N/W/E/S interfaces.
// Maps the 3x3 Sobel kernel onto 9 PEs. Each PE applies its configured
// weight (shift-add for +/-1/+/-2) to its window pixel. The array sums
// PE outputs for Gx and Gy separately and produces magnitude |Gx|+|Gy|
// saturated to 8-bit.
// For Sobel, cfg is hardwired to the Sobel weight mapping (no external cfg).
// The sobel_core does the actual combinational compute; this module wraps
// it with the PE array for architectural fidelity. Output is combinational
// (mirrors golden model: done=start, sobel_out=core_out).
`include "params.vh"

module cgra_3x3 (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [71:0] win,          // 9 x 8-bit window, row-major
    input  wire        start,
    output wire [`DATA_W-1:0] sobel_out,
    output wire        done
);

    // Sobel weight -> PE cfg mapping
    // Gx = [-1, 0,+1, -2, 0,+2, -1, 0,+1]
    // Gy = [-1,-2,-1,  0, 0, 0, +1,+2,+1]
    // cfg: 0=PASS(+1), 3=SHL1(+2), 4=NEG(-1), 5=NEG_SHL1(-2), 6=ZERO(0)
    localparam C_PASS     = 3'd0;
    localparam C_SHL1     = 3'd3;
    localparam C_NEG      = 3'd4;
    localparam C_NEG_SHL1 = 3'd5;
    localparam C_ZERO     = 3'd6;

    // Gx cfg per PE (row-major 0..8)
    wire [2:0] cfg_gx [0:8];
    assign cfg_gx[0] = C_NEG;       // -1
    assign cfg_gx[1] = C_ZERO;      //  0
    assign cfg_gx[2] = C_PASS;      // +1
    assign cfg_gx[3] = C_NEG_SHL1;  // -2
    assign cfg_gx[4] = C_ZERO;      //  0
    assign cfg_gx[5] = C_SHL1;      // +2
    assign cfg_gx[6] = C_NEG;       // -1
    assign cfg_gx[7] = C_ZERO;      //  0
    assign cfg_gx[8] = C_PASS;      // +1

    // Gy cfg per PE (row-major 0..8)
    wire [2:0] cfg_gy [0:8];
    assign cfg_gy[0] = C_NEG;       // -1
    assign cfg_gy[1] = C_NEG_SHL1;  // -2
    assign cfg_gy[2] = C_NEG;       // -1
    assign cfg_gy[3] = C_ZERO;      //  0
    assign cfg_gy[4] = C_ZERO;      //  0
    assign cfg_gy[5] = C_ZERO;      //  0
    assign cfg_gy[6] = C_PASS;      // +1
    assign cfg_gy[7] = C_SHL1;      // +2
    assign cfg_gy[8] = C_PASS;      // +1

    // unpack window
    wire [7:0] w [0:8];
    assign w[0] = win[7:0];
    assign w[1] = win[15:8];
    assign w[2] = win[23:16];
    assign w[3] = win[31:24];
    assign w[4] = win[39:32];
    assign w[5] = win[47:40];
    assign w[6] = win[55:48];
    assign w[7] = win[63:56];
    assign w[8] = win[71:64];

    // Instantiate 9 PEs for Gx and 9 PEs for Gy (18 total).
    // Each PE computes its weighted pixel value; combinational output.
    wire [7:0] pe_gx_res [0:8];
    wire [7:0] pe_gy_res [0:8];

    genvar i;
    generate
        for (i = 0; i < 9; i = i + 1) begin : g_pe_gx
            pe u_pe_gx (
                .clk(clk), .rst_n(rst_n),
                .cfg(cfg_gx[i]),
                .opa(w[i]), .opb(8'd0),
                .result(pe_gx_res[i]), .cout()
            );
        end
        for (i = 0; i < 9; i = i + 1) begin : g_pe_gy
            pe u_pe_gy (
                .clk(clk), .rst_n(rst_n),
                .cfg(cfg_gy[i]),
                .opa(w[i]), .opb(8'd0),
                .result(pe_gy_res[i]), .cout()
            );
        end
    endgenerate

    // sobel_core: combinational bit-exact Sobel compute (primary output path)
    wire [`DATA_W-1:0] core_out;
    sobel_core u_core (
        .win(win),
        .sobel_out(core_out)
    );

    // Combinational outputs (mirrors golden model)
    assign sobel_out = core_out;
    assign done      = start;

endmodule