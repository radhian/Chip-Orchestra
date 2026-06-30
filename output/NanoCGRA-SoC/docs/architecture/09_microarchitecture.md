# NanoCGRA-SoC Microarchitecture

Version: v0.1

---

# 1. Introduction

This document describes the internal microarchitecture of NanoCGRA-SoC.

Unlike the architecture overview, this document focuses on implementation
decisions, trade-offs, and design rationale.

The primary design goals are:

- Extremely small silicon area
- Low power consumption
- Simple verification
- Modular RTL
- First-silicon success

The initial implementation intentionally avoids unnecessary complexity
while providing a scalable foundation for future SoC revisions.

---

# 2. Design Philosophy

NanoCGRA-SoC follows five principles.

## 2.1 Keep Everything Memory Mapped

Every peripheral behaves like memory.

The CPU never communicates using dedicated instructions.

Instead,

CPU

↓

Read / Write

↓

Interconnect

↓

Peripheral

This greatly simplifies software.

---

## 2.2 Keep Modules Independent

Each RTL module has one responsibility.

Example

UART

- register interface
- transmitter
- receiver
- interrupt controller

instead of one large RTL file.

Advantages

- Easier verification
- Better reuse
- Smaller synthesis units
- Cleaner timing reports

---

## 2.3 Minimize Global Logic

The top level never contains logic.

nano_soc_top.v only performs

- module instantiation
- signal routing

All functionality exists inside dedicated modules.

---

## 2.4 One Clock Domain

Current implementation uses

20 MHz

System Clock

All peripherals share the same clock.

Advantages

- simpler timing
- easier verification
- no CDC

Future versions may introduce

CGRA Clock

without changing the existing bus.

---

## 2.5 Simplicity First

This project intentionally avoids

- pipelines
- caches
- speculative execution
- out-of-order logic

The objective is reliable silicon.

---

# 3. SMPB Bus

The Simple Memory Peripheral Bus (SMPB)
connects the CPU to all peripherals.

Master

FAZYRV CPU

Slaves

SRAM

UART

CGRA

GPIO

Timer

Bus Signals

Request

valid

write

addr

wdata

wstrb

Response

ready

rdata

error

A transaction completes when

valid = 1

ready = 1

---

# 4. Address Decoder

Address decoding uses

addr[31:16]

instead of the entire address.

Example

0x0002_0010

↓

0x0002

↓

UART

Advantages

- very small decoder
- low area
- low delay

Estimated logic

≈35 gates

---

# 5. Interconnect

The interconnect performs exactly four tasks.

1

Address Decode

↓

2

Read Multiplexing

↓

3

Ready Multiplexing

↓

4

Error Multiplexing

No additional logic is implemented.

The interconnect is intentionally passive.

---

# 6. Default Slave

Invalid accesses are routed to

default_slave.v

Response

ready = 1

error = 1

rdata = DEAD_BEEF

Advantages

The CPU never hangs due to an invalid address.

---

# 7. UART

UART is divided into independent blocks.

uart_top

├── uart_regs

├── uart_tx

├── uart_rx

├── baud_gen

├── fifo_sync

├── uart_interrupt

Each block has a single responsibility.

---

# 8. UART Transmitter

The transmitter uses

4-state FSM

instead of

11-state FSM.

States

IDLE

↓

START

↓

DATA

↓

STOP

Bit transmission uses

3-bit counter

Advantages

- fewer gates
- simpler timing
- easier verification

Estimated gates

≈220

---

# 9. UART Receiver

The receiver uses

16x oversampling.

Instead of sampling every bit edge,

it samples

middle of the bit.

Advantages

Higher noise tolerance

Better baud mismatch tolerance

Lower framing error probability

Estimated gates

≈350

Future improvement

Majority vote

7

8

9

sample positions

---

# 10. FIFO

Both TX and RX contain independent FIFOs.

Purpose

CPU

↓

FIFO

↓

UART

Advantages

CPU never waits for UART timing.

Future versions may increase FIFO depth.

---

# 11. Interrupt Controller

Interrupt Sources

TX Empty

RX Ready

RX Overflow

Framing Error

Interrupts are individually masked.

The controller generates one interrupt output.

---

# 12. Clocking

Current

20 MHz

Future

Optional

CGRA Clock

The current implementation has

one synchronous domain.

---

# 13. Reset

Reset

Active Low

rst_n

All registers initialize during reset.

No asynchronous data paths exist.

---

# 14. Estimated Area

Interconnect

≈190 gates

UART

≈1700 gates

Glue Logic

≈200 gates

Current SoC

≈2100 gates

excluding

SRAM

CPU

CGRA

---

# 15. Estimated Dynamic Power

20 MHz

Interconnect

<1 µW

UART Idle

<1 µW

UART Active

5–7 µW

Current SoC Logic

<10 µW

excluding SRAM and CPU.

---

# 16. Verification Strategy

Each module is verified independently.

Example

addr_decoder

↓

read_mux

↓

UART

↓

Interconnect

↓

Top-level SoC

No module is verified only at SoC level.

---

# 17. Future Roadmap

v0.2

FAZYRV Integration

SRAM

Boot ROM

GPIO

Timer

v0.3

2×2 CGRA

Configuration Registers

DMA

Interrupt Controller

v0.4

Performance Optimization

Pipeline Improvements

Power Gating

Clock Gating

---

# 18. Design Goals

Area

★★★★★

Power

★★★★★

Performance

★★☆☆☆

Complexity

★☆☆☆☆

Verification

★★★★★

Tapeout Readiness

★★★★★