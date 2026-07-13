//============================================================================
// nano_controller.v  -  FSM-ONLY orchestrator for the CGRA.
//   NO CPU, NO program counter, NO register file. Pure finite-state machine
//   plus a few datapath latches (operand captures / SRAM address).
//   Flow on START: read operand-A and operand-B from SRAM, load the CGRA,
//   execute one evaluation, store the CGRA result back to SRAM.
//   Synchronous reset, no latches, no tri-state.
//============================================================================
`include "params.vh"

module nano_controller #(
    parameter DW = `DATA_WIDTH,
    parameter AW = `SRAM_AW
) (
    input  wire            clk,
    input  wire            rst_n,

    input  wire            start_pulse,   // 1-cycle START strobe from bus

    // operand/result SRAM addresses (from CGRA config regs 0x94/0x95/0x96)
    input  wire [AW-1:0]   opa_addr,
    input  wire [AW-1:0]   opb_addr,
    input  wire [AW-1:0]   res_addr,

    input  wire [DW-1:0]   sram_rdata,    // SRAM read data (shared port)
    input  wire [DW-1:0]   cgra_result,   // CGRA read-out

    // CGRA control
    output wire            cgra_load_cfg,
    output wire            cgra_load_data,
    output wire            cgra_en,
    output reg  [DW-1:0]   data_a,
    output reg  [DW-1:0]   data_b,

    // SRAM master interface (valid while busy)
    output wire            m_sram_we,
    output reg  [AW-1:0]   m_sram_addr,
    output wire [DW-1:0]   m_sram_din,

    // status
    output wire            busy,
    output reg             done
);
    reg [2:0] state;

    // ---- Combinational Moore outputs ---------------------------------
    assign cgra_load_cfg  = (state == `ST_LOAD);
    assign cgra_load_data = (state == `ST_LOAD);
    assign cgra_en        = (state == `ST_EXEC);
    assign m_sram_we      = (state == `ST_STORE);
    assign m_sram_din     = cgra_result;
    assign busy           = (state != `ST_IDLE);

    // ---- Sequential FSM + datapath -----------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            state       <= `ST_IDLE;
            data_a      <= {DW{1'b0}};
            data_b      <= {DW{1'b0}};
            m_sram_addr <= {AW{1'b0}};
            done        <= 1'b0;
        end else begin
            case (state)
                `ST_IDLE: begin
                    if (start_pulse) begin
                        done        <= 1'b0;
                        m_sram_addr <= opa_addr;   // present operand-A address
                        state       <= `ST_RD_A;
                    end
                end
                `ST_RD_A: begin
                    m_sram_addr <= opb_addr;       // present operand-B address
                    state       <= `ST_RD_B;
                end
                `ST_RD_B: begin
                    data_a <= sram_rdata;          // mem[opa_addr] now valid
                    state  <= `ST_LOAD;
                end
                `ST_LOAD: begin
                    data_b <= sram_rdata;          // mem[opb_addr] now valid
                    state  <= `ST_EXEC;
                end
                `ST_EXEC: begin
                    m_sram_addr <= res_addr;       // present result address
                    state       <= `ST_STORE;
                end
                `ST_STORE: begin
                    done  <= 1'b1;                 // result committed this edge
                    state <= `ST_DONE;
                end
                `ST_DONE: begin
                    state <= `ST_IDLE;
                end
                default: state <= `ST_IDLE;
            endcase
        end
    end
endmodule
