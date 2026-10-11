//============================================================================
// pe.v  -  NanoCGRA-Lite Processing Element
//   * 8-bit Arithmetic Unit (ADD/SUB/AND/OR/XOR/PASS)
//   * 8x8 combinational multiplier
//   * MAC (multiply-accumulate) with local accumulator
//   * local data register + config register
//   * N/S/E/W nearest-neighbor routing (operand-B source select)
// Fully synchronous, synchronous reset, no latches, no tri-state.
//============================================================================
`include "params.vh"

module pe #(
    parameter DW = `DATA_WIDTH
) (
    input  wire            clk,
    input  wire            rst_n,

    // control strobes from the Nano Controller
    input  wire            load_cfg,   // capture cfg_in into config register
    input  wire            load_data,  // capture data_in into local register
    input  wire            en,         // evaluate/accumulate this cycle

    // configuration + data load buses
    input  wire [DW-1:0]   cfg_in,     // {reserved[2:0], bsel[1:0], op[2:0]}
    input  wire [DW-1:0]   data_in,    // local register load value

    // nearest-neighbor routing inputs
    input  wire [DW-1:0]   src_n,
    input  wire [DW-1:0]   src_s,
    input  wire [DW-1:0]   src_e,
    input  wire [DW-1:0]   src_w,

    // registered result (routed to neighbors and read-out)
    output wire [DW-1:0]   result
);
    // ---- Configuration register --------------------------------------
    reg  [DW-1:0] cfg_reg;      // config register
    reg  [DW-1:0] local_reg;    // local operand-A register
    reg  [2*DW-1:0] acc;        // MAC accumulator (16-bit)

    wire [2:0] op   = cfg_reg[2:0];
    wire [1:0] bsel = cfg_reg[4:3];

    // ---- Operand-B routing mux (N/S/E/W) -----------------------------
    reg [DW-1:0] opb;
    always @(*) begin
        case (bsel)
            `SEL_N:  opb = src_n;
            `SEL_S:  opb = src_s;
            `SEL_E:  opb = src_e;
            `SEL_W:  opb = src_w;
            default: opb = src_n;
        endcase
    end

    // ---- 8x8 multiplier ----------------------------------------------
    wire [2*DW-1:0] product = local_reg * opb;

    // ---- Arithmetic unit ---------------------------------------------
    reg [DW-1:0] alu_r;
    always @(*) begin
        case (op)
            `OP_ADD:  alu_r = local_reg + opb;
            `OP_SUB:  alu_r = local_reg - opb;
            `OP_AND:  alu_r = local_reg & opb;
            `OP_OR :  alu_r = local_reg | opb;
            `OP_XOR:  alu_r = local_reg ^ opb;
            `OP_MUL:  alu_r = product[DW-1:0];
            `OP_MAC:  alu_r = acc[DW-1:0];
            `OP_PASS: alu_r = local_reg;
            default:  alu_r = local_reg;
        endcase
    end

    // ---- Sequential state (synchronous reset) ------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            cfg_reg   <= {DW{1'b0}};
            local_reg <= {DW{1'b0}};
            acc       <= {(2*DW){1'b0}};
        end else begin
            if (load_cfg)  cfg_reg   <= cfg_in;
            if (load_data) local_reg <= data_in;
            // Reconfiguring the PE clears the MAC accumulator (start a new
            // accumulation cleanly). Clear takes priority over accumulate.
            if (load_cfg) begin
                acc <= {(2*DW){1'b0}};
            end else if (en) begin
                if (op == `OP_MAC)
                    acc <= acc + product;              // accumulate
                else
                    acc <= {{DW{1'b0}}, alu_r};         // latch single-op result
            end
        end
    end

    assign result = acc[DW-1:0];
endmodule
