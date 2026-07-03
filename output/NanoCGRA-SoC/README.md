# Nano CGRA SoC 

Open-source Nano CGRA SoC targeting GF180MCU.

**Technology:** GF180MCU  
**Target Die Size:** 0.25 mm × 0.25 mm (0.0625 mm²)

---

# Motivation & Design Goals

## Motivation

- Demonstrate software-controlled CGRA acceleration
- Minimal-area SoC for GF180MCU
- Simple architecture for first-silicon success
- Low power and easy verification

## Design Targets

| Component | Specification |
|-----------|---------------|
| CPU | FazyRV RV32I (8-bit chunksize) |
| Accelerator | 2×2 CGRA |
| Processing Element | 8-bit ALU |
| SRAM | 1 KB |
| Peripheral | UART |
| Interface | Memory-Mapped |


## Overall Architecture

```mermaid
flowchart LR

SPEC["Application / Firmware"]

CPU["FazyRV RV32I"]

CGRA["2×2 CGRA"]

SRAM["1 KB SRAM"]

UART["UART"]

SPEC --> CPU

CPU --> CGRA
CPU --> SRAM
CPU --> UART
```

**Key Takeaway**

A minimal SoC that demonstrates software-controlled CGRA acceleration while prioritizing low area, low power, and implementation simplicity.

---

# System Architecture

## Top-Level Architecture

```mermaid
flowchart TB

CPU["FazyRV RV32I CPU"]

BUS["Memory-Mapped Interconnect"]

SRAM["1 KB SRAM"]

CGRA["2×2 CGRA Accelerator"]

UART["UART"]

CPU --> BUS

BUS --> SRAM
BUS --> CGRA
BUS --> UART
```

### CPU

- Executes firmware
- Configures CGRA
- Reads computation results

### Memory-Mapped Interconnect

- Simple address decoder
- Minimal routing overhead
- Easy integration

### Peripherals

- SRAM stores firmware and data
- UART provides programming and debugging

---

# CGRA Architecture

## 2×2 CGRA Accelerator

```mermaid
flowchart TB

subgraph CGRA["2×2 CGRA"]

PE0["PE0"]

PE1["PE1"]

PE2["PE2"]

PE3["PE3"]

PE0 --- PE1
PE2 --- PE3

PE0 --- PE2
PE1 --- PE3

end
```

### Processing Element

Each PE supports only five operations:

- ADD
- SUB
- AND
- OR
- PASS

### Configuration Registers

```text
Operation
Source A
Source B
Destination
Enable
```

**Design Philosophy**

- Small datapath
- Simple routing
- Minimal configuration bits
- Easy verification

---

# Software-Controlled Execution

## Execution Flow

```mermaid
flowchart LR

CPU["CPU Firmware"]

CFG["Write Configuration"]

DATA["Write Input Data"]

EXEC["CGRA Execute"]

RESULT["Read Result"]

CPU --> CFG
CFG --> DATA
DATA --> EXEC
EXEC --> RESULT
RESULT --> CPU
```

## Memory Map

| Address | Function |
|---------|----------|
| 0x0000 | SRAM |
| 0x1000 | CGRA Configuration |
| 0x1100 | CGRA Data |
| 0x2000 | UART |

### Advantages

- Memory-mapped programming model
- No DMA required
- Simple software interface
- Straightforward debugging

---

# Design Tradeoffs & Summary

## Area Optimization

```mermaid
mindmap
  root((Nano CGRA))
    Minimal CPU
      FazyRV RV32I
    Small CGRA
      2×2
      8-bit PE
    Simple Memory
      1 KB SRAM
    Simple Bus
      Memory Mapped
    Simple IO
      UART
```

## Design Decisions

- Lightweight RV32I host processor
- Four 8-bit processing elements
- Memory-mapped accelerator interface
- Lightweight interconnect
- Small on-chip SRAM
- No DMA or cache
- Optimized for first-silicon success

## Expected Outcome

- Minimal silicon area
- Low routing complexity
- Low power consumption
- Easy verification
- Software-controlled acceleration
- Fits the GF180MCU 0.25 mm × 0.25 mm target
