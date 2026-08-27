// pe.v — single Processing Element (8-bit ALU/MAC).
// cfg encodings:
//   0 : pass opa            (result = opa)
//   1 : multiply opa*opb    (result = opa*opb, low 8 bits)  [weight MAC]
//   2 : add  opa + opb      (result = opa + opb)
//   3 : shift-left-1 opa    (result = opa << 1)  [weight = +2]
//   4 : negate opa          (result = -opa)      [weight = -1]
//   5 : shift-left-1 + neg  (result = -(opa<<1)) [weight = -2]
//   6 : pass 0              (result = 0)         [weight = 0]
//   7 : abs opa             (result = |opa|)
// Combinational result (mirrors golden model). cout mirrors result.
`include "params.vh"

module pe (
    input  wire               clk,
    input  wire               rst_n,
    input  wire [2:0]         cfg,
    input  wire [`DATA_W-1:0] opa,
    input  wire [`DATA_W-1:0] opb,
    output reg  [`DATA_W-1:0] result,
    output reg  [`DATA_W-1:0] cout
);

    // cfg encodings
    localparam C_PASS     = 3'd0;
    localparam C_MUL      = 3'd1;
    localparam C_ADD      = 3'd2;
    localparam C_SHL1     = 3'd3;
    localparam C_NEG      = 3'd4;
    localparam C_NEG_SHL1 = 3'd5;
    localparam C_ZERO     = 3'd6;
    localparam C_ABS      = 3'd7;

    // Combinational — golden model computes result immediately (no register).
    // rst_n forces 0 to match golden reset behaviour.
    always @(*) begin
        if (!rst_n) begin
            result = {`DATA_W{1'b0}};
            cout   = {`DATA_W{1'b0}};
        end else begin
            case (cfg)
                C_PASS: begin
                    result = opa;
                    cout   = opa;
                end
                C_MUL: begin
                    result = (opa * opb[`DATA_W-1:0]);
                    cout   = (opa * opb[`DATA_W-1:0]);
                end
                C_ADD: begin
                    result = opa + opb;
                    cout   = opa + opb;
                end
                C_SHL1: begin
                    result = {opa[`DATA_W-2:0], 1'b0};
                    cout   = {opa[`DATA_W-2:0], 1'b0};
                end
                C_NEG: begin
                    result = (~opa) + 8'd1;
                    cout   = (~opa) + 8'd1;
                end
                C_NEG_SHL1: begin
                    result = (~{opa[`DATA_W-2:0], 1'b0}) + 8'd1;
                    cout   = (~{opa[`DATA_W-2:0], 1'b0}) + 8'd1;
                end
                C_ZERO: begin
                    result = {`DATA_W{1'b0}};
                    cout   = {`DATA_W{1'b0}};
                end
                C_ABS: begin
                    if (opa[7]) begin
                        result = (~opa) + 8'd1;
                        cout   = (~opa) + 8'd1;
                    end else begin
                        result = opa;
                        cout   = opa;
                    end
                end
                default: begin
                    result = {`DATA_W{1'b0}};
                    cout   = {`DATA_W{1'b0}};
                end
            endcase
        end
    end

endmodule