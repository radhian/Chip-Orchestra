module ChipOrchestraDualCorePads #(parameter UART_CLK_PER_BIT=87)(
input wire clk,
input wire rst_n,
input wire uart_rx,
input wire fa_a,
input wire fa_b,
input wire fa_cin,
output wire uart_tx,
output wire fa_sum,
output wire fa_cout
);
supply1 VDD, DVDD;
supply0 VSS, DVSS;
wire core_clk,core_rst_n,core_uart_rx,core_fa_a,core_fa_b,core_fa_cin,core_uart_tx,core_fa_sum,core_fa_cout;
ChipOrchestraDualCore #(.UART_CLK_PER_BIT(UART_CLK_PER_BIT)) u_core (.clk(core_clk),.rst_n(core_rst_n),.uart_rx(core_uart_rx),.fa_a(core_fa_a),.fa_b(core_fa_b),.fa_cin(core_fa_cin),.uart_tx(core_uart_tx),.fa_sum(core_fa_sum),.fa_cout(core_fa_cout));
gf180mcu_fd_io__in_c pad_clk (.PAD(clk),.Y(core_clk),.PU(1'b0),.PD(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__in_c pad_rst_n (.PAD(rst_n),.Y(core_rst_n),.PU(1'b0),.PD(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__bi_t pad_uart_rx (.PAD(uart_rx),.Y(core_uart_rx),.A(1'b0),.IE(1'b1),.OE(1'b0),.PU(1'b0),.PD(1'b0),.CS(1'b0),.SL(1'b0),.PDRV0(1'b0),.PDRV1(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__in_c pad_fa_a (.PAD(fa_a),.Y(core_fa_a),.PU(1'b0),.PD(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__in_c pad_fa_b (.PAD(fa_b),.Y(core_fa_b),.PU(1'b0),.PD(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__in_c pad_fa_cin (.PAD(fa_cin),.Y(core_fa_cin),.PU(1'b0),.PD(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__bi_t pad_uart_tx (.PAD(uart_tx),.A(core_uart_tx),.Y(),.IE(1'b0),.OE(1'b1),.PU(1'b0),.PD(1'b0),.CS(1'b0),.SL(1'b0),.PDRV0(1'b0),.PDRV1(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__bi_t pad_fa_sum (.PAD(fa_sum),.A(core_fa_sum),.Y(),.IE(1'b0),.OE(1'b1),.PU(1'b0),.PD(1'b0),.CS(1'b0),.SL(1'b0),.PDRV0(1'b0),.PDRV1(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
gf180mcu_fd_io__bi_t pad_fa_cout (.PAD(fa_cout),.A(core_fa_cout),.Y(),.IE(1'b0),.OE(1'b1),.PU(1'b0),.PD(1'b0),.CS(1'b0),.SL(1'b0),.PDRV0(1'b0),.PDRV1(1'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));
endmodule
