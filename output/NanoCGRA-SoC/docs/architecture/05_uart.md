# UART Peripheral

The UART peripheral contains:

uart_top

├── uart_regs

├── uart_tx

├── uart_rx

├── baud_gen

├── fifo_sync (TX)

├── fifo_sync (RX)

└── uart_interrupt

Supported Features

- 8-bit data
- 1 stop bit
- No parity
- Configurable baud rate
- Memory mapped registers
- Interrupt support
- TX FIFO
- RX FIFO

Future Features

- Loopback mode
- Parity
- RTS/CTS