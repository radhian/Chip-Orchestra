# SoC Architecture

The current SoC architecture consists of:

                +----------------+
                |   FAZYRV CPU   |
                +-------+--------+
                        |
                    SMPB BUS
                        |
            +-----------+------------+
            |                        |
      SMPB Interconnect        Future DMA
            |
    +-------+-------+-------+
    |       |       |       |
  SRAM    UART    CGRA    GPIO

The interconnect performs:

- Address decoding
- Read data multiplexing
- Ready multiplexing
- Error multiplexing

The top-level SoC contains no bus logic.

Its only purpose is module integration.