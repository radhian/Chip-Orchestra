//============================================================================
// cgra.v  -  3x3 CGRA array (9 PEs) with nearest-neighbor (N/S/E/W) routing.
//   Grid layout:            col0      col1      col2
//                    row0 [ pe00 ] [ pe01 ] [ pe02 ]
//                    row1 [ pe10 ] [ pe11 ] [ pe12 ]
//                    row2 [ pe20 ] [ pe21 ] [ pe22 ]
//   Canonical read-out = PE(0,0). All nine PEs are wired in the square mesh so
//   the nearest-neighbor fabric is present and synthesizable.
//
//   Routing convention (identical to the 2x2 baseline, generalized):
//     src_n = (row==0)      ? data_b : result(row-1,col)   // north boundary = B
//     src_w = (col==0)      ? data_a : result(row,col-1)   // west  boundary = A
//     src_s = (row==ROWS-1) ? 0      : result(row+1,col)
//     src_e = (col==COLS-1) ? 0      : result(row,col+1)
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

    // per-PE configuration (0x90..0x98)
    input  wire [DW-1:0]   cfg0,
    input  wire [DW-1:0]   cfg1,
    input  wire [DW-1:0]   cfg2,
    input  wire [DW-1:0]   cfg3,
    input  wire [DW-1:0]   cfg4,
    input  wire [DW-1:0]   cfg5,
    input  wire [DW-1:0]   cfg6,
    input  wire [DW-1:0]   cfg7,
    input  wire [DW-1:0]   cfg8,

    // external operands presented on the array boundary
    input  wire [DW-1:0]   data_a,
    input  wire [DW-1:0]   data_b,

    output wire [DW-1:0]   result
);
    wire [DW-1:0] r00, r01, r02,
                  r10, r11, r12,
                  r20, r21, r22;

    // ---- Row 0 --------------------------------------------------------
    // PE(0,0): N=data_b, W=data_a, S=r10, E=r01
    pe #(.DW(DW)) pe00 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg0), .data_in(data_a),
        .src_n(data_b), .src_s(r10), .src_e(r01), .src_w(data_a),
        .result(r00));

    // PE(0,1): N=data_b, W=r00, S=r11, E=r02
    pe #(.DW(DW)) pe01 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg1), .data_in(data_a),
        .src_n(data_b), .src_s(r11), .src_e(r02), .src_w(r00),
        .result(r01));

    // PE(0,2): N=data_b, W=r01, S=r12, E=boundary(0)
    pe #(.DW(DW)) pe02 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg2), .data_in(data_a),
        .src_n(data_b), .src_s(r12), .src_e({DW{1'b0}}), .src_w(r01),
        .result(r02));

    // ---- Row 1 --------------------------------------------------------
    // PE(1,0): N=r00, W=data_a, S=r20, E=r11
    pe #(.DW(DW)) pe10 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg3), .data_in(data_a),
        .src_n(r00), .src_s(r20), .src_e(r11), .src_w(data_a),
        .result(r10));

    // PE(1,1): N=r01, W=r10, S=r21, E=r12
    pe #(.DW(DW)) pe11 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg4), .data_in(data_a),
        .src_n(r01), .src_s(r21), .src_e(r12), .src_w(r10),
        .result(r11));

    // PE(1,2): N=r02, W=r11, S=r22, E=boundary(0)
    pe #(.DW(DW)) pe12 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg5), .data_in(data_a),
        .src_n(r02), .src_s(r22), .src_e({DW{1'b0}}), .src_w(r11),
        .result(r12));

    // ---- Row 2 --------------------------------------------------------
    // PE(2,0): N=r10, W=data_a, S=boundary(0), E=r21
    pe #(.DW(DW)) pe20 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg6), .data_in(data_a),
        .src_n(r10), .src_s({DW{1'b0}}), .src_e(r21), .src_w(data_a),
        .result(r20));

    // PE(2,1): N=r11, W=r20, S=boundary(0), E=r22
    pe #(.DW(DW)) pe21 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg7), .data_in(data_a),
        .src_n(r11), .src_s({DW{1'b0}}), .src_e(r22), .src_w(r20),
        .result(r21));

    // PE(2,2): N=r12, W=r21, S=boundary(0), E=boundary(0)
    pe #(.DW(DW)) pe22 (
        .clk(clk), .rst_n(rst_n),
        .load_cfg(load_cfg), .load_data(load_data), .en(en),
        .cfg_in(cfg8), .data_in(data_a),
        .src_n(r12), .src_s({DW{1'b0}}), .src_e({DW{1'b0}}), .src_w(r21),
        .result(r22));

    // Canonical CGRA output is PE(0,0).
    assign result = r00;
endmodule
