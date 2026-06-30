module uart_top
(
    // Clock / Reset
    clk,
    rst_n,

    // SMPB Register Interface
    bus_valid,
    bus_write,
    bus_addr,
    bus_wdata,
    bus_rdata,
    bus_ready,

    // UART Pins
    uart_tx,
    uart_rx,

    // Interrupt
    irq
);