# SMPB Bus

SMPB (Simple Memory Peripheral Bus) is a lightweight memory-mapped
bus designed specifically for NanoCGRA-SoC.

## Master Interface

valid
write
addr[31:0]
wdata[31:0]
wstrb[3:0]

## Slave Response

rdata[31:0]
ready
error

## Transaction

CPU

↓

Address Decode

↓

Peripheral

↓

Response

↓

CPU

One transfer is completed whenever

valid = 1

ready = 1

The protocol supports wait states.

Future versions may support multiple bus masters.