//============================================================================
// cgra.v  -  2x2 CGRA array (4 PEs) with nearest-neighbor (N/S/E/W) routing.
//   Grid layout:            col0      col1
//                    row0 [ pe00 ] [ pe01 ]
//                    row1 [ pe10 ] [ pe11 ]
//   Canonical read-out = PE(0,0). All four PEs are wired in the mesh so the
//   nearest-neighbor fabric is present and synthesizable.
//============================================================================
`include "params.vh"

module cgra #(
    parameter DW = `DATA_WIDTH
) (
    input  wire            clk,
    input  wire            rst_n,

    input  wire            load_cfg,
    input  wire            load_data,
    input  wire            en,

    // per-PE configuration (0x90..0x93)
    input  wire [DW-1:0]   cfg0,
    input  wire [DW-1:0]   cfg1,
    input  wire [DW-1:0]   cfg2,
    input  wire [DW-1:0]   cfg3,

    // external operands presented on the array boundary
    input  wire [DW-1:0]   data_a,
    input  wire [DW-1:0]   data_b,

    output wire [DW-1:0]   result
);
    wire [DW-1:0] r00, r01, r10, r11;

    // PE(0,0): local=A, N=B, W=A(boundary), S=r10, E=r01
    pe #(.DW(DW)) pe00 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg0), .data_in(data_a),
        .src_n(data_b), .src_s(r10), .src_e(r01), .src_w(data_a),
        .result(r00));

    // PE(0,1): local=A, N=B, W=r00, S=r11, E=boundary(0)
    pe #(.DW(DW)) pe01 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg1), .data_in(data_a),
        .src_n(data_b), .src_s(r11), .src_e({DW{1'b0}}), .src_w(r00),
        .result(r01));

    // PE(1,0): local=A, N=r00, W=A(boundary), S=boundary(0), E=r11
    pe #(.DW(DW)) pe10 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg2), .data_in(data_a),
        .src_n(r00), .src_s({DW{1'b0}}), .src_e(r11), .src_w(data_a),
        .result(r10));

    // PE(1,1): local=A, N=r01, W=r10, S=boundary(0), E=boundary(0)
    pe #(.DW(DW)) pe11 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg3), .data_in(data_a),
        .src_n(r01), .src_s({DW{1'b0}}), .src_e({DW{1'b0}}), .src_w(r10),
        .result(r11));

    // Canonical CGRA output is PE(0,0).
    assign result = r00;
endmodule
