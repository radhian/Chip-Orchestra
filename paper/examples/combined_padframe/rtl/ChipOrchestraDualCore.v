module ChipOrchestraDualCore #(parameter UART_CLK_PER_BIT=87)(
    input wire clk, rst_n, uart_rx,
    output wire uart_tx,
    input wire fa_a, fa_b, fa_cin,
    output wire fa_sum, fa_cout
);
    NanoCGRA_Lite #(.UART_CLK_PER_BIT(UART_CLK_PER_BIT)) u_cgra (
        .clk(clk), .rst_n(rst_n), .uart_rx(uart_rx), .uart_tx(uart_tx)
    );
    fulladder u_fulladder (
        .a(fa_a), .b(fa_b), .cin(fa_cin), .sum(fa_sum), .cout(fa_cout)
    );
endmodule
