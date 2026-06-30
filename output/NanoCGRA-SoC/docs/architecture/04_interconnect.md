# SMPB Interconnect

Modules

- addr_decoder.v
- read_mux.v
- ready_mux.v
- error_mux.v
- default_slave.v
- arbiter_stub.v
- smpb_interconnect.v

Responsibilities

- Decode address
- Select one peripheral
- Forward read data
- Forward ready
- Forward error

Priority

SRAM
↓

CGRA
↓

UART
↓

GPIO
↓

TIMER
↓

DEFAULT

Invalid accesses are handled by default_slave.