`include "cgra_defs.svh"
module ALU(
  input  [4:0]  io_config,
  input  [31:0] io_in_0,
  input  [31:0] io_in_1,
  output [31:0] io_out
);
  wire [31:0] _T_4 = io_in_0 + io_in_1; // @[Operations.scala 131:41]
  wire [31:0] _T_8 = io_in_0 - io_in_1; // @[Operations.scala 133:41]
  wire [63:0] _T_11 = io_in_0 * io_in_1; // @[Operations.scala 135:41]
  wire  _T_12 = 5'h0 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_13 = _T_12 ? io_in_0 : 32'h0; // @[Mux.scala 80:57]
  wire  _T_14 = 5'h1 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_15 = _T_14 ? _T_4 : _T_13; // @[Mux.scala 80:57]
  wire  _T_16 = 5'h2 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_17 = _T_16 ? _T_8 : _T_15; // @[Mux.scala 80:57]
  wire  _T_18 = 5'h3 == io_config; // @[Mux.scala 80:60]
  wire [63:0] _T_19 = _T_18 ? _T_11 : {{32'd0}, _T_17}; // @[Mux.scala 80:57]
  assign io_out = _T_19[31:0]; // @[ALU.scala 26:10]
endmodule
