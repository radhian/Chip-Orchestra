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


# SoC Architecture

## SoC Block Diagram
```mermaid
flowchart TD
    CPU[FazyRV CPU <br/> RV32I 8-bit chunk]
    Bus[SMPB Bus <br/> Memory-mapped interconnect]
    SRAM[SRAM <br/> 1 KB]
    CGRA[CGRA 2x2 <br/> Accelerator]
    UART[UART]
    GPIO[GPIO <br/> Future]
    Timer[Timer <br/> Future]
    
    CPU <-->|Single Master| Bus
    Bus <-->|Slave: 0x0000_0000| SRAM
    Bus <-->|Slave: 0x0001_0000| CGRA
    Bus <-->|Slave: 0x0002_0000| UART
    Bus <-->|Slave: 0x0003_0000| GPIO
    Bus <-->|Slave: 0x0004_0000| Timer
```

## Memory Map
| Address Range | Peripheral | Size / Note |
| --- | --- | --- |
| `0x0000_0000` | SRAM | 1 KB |
| `0x0001_0000` | CGRA Config Registers | - |
| `0x0002_0000` | UART | - |
| `0x0003_0000` | GPIO | Future |
| `0x0004_0000` | Timer | Future |

## CGRA Microarchitecture

### 2×2 PE Grid
```mermaid
flowchart TD
    In[Input Port]
    PE00[PE 0,0]
    PE01[PE 0,1]
    PE10[PE 1,0]
    PE11[PE 1,1]
    Out[CGRA Output / Status Regs]
    
    In --> PE00
    In --> PE10
    
    PE00 -->|Neighbor N/W| PE01
    PE00 -->|Neighbor N/W| PE10
    PE10 -->|Neighbor N/W| PE11
    PE01 -->|Neighbor N/W| PE11
    
    PE00 -. Config Reg .-> PE00
    PE01 -. Config Reg .-> PE01
    PE10 -. Config Reg .-> PE10
    PE11 -. Config Reg .-> PE11
    
    PE11 --> Out
```

*Note: The host CPU configures the CGRA by writing to memory-mapped configuration registers.*

### PE Configuration Register Layout
| Field Name | Bits | Description |
| --- | --- | --- |
| `op` | `[2:0]` | Operation code for the PE |
| `in_sel_a` | `[1:0]` | Input A selection (N/W neighbor or input port) |
| `in_sel_b` | `[1:0]` | Input B selection (N/W neighbor or input port) |

### Supported Operations
| Operation | Encoding (`op[2:0]`) | Description |
| --- | --- | --- |
| ADD | 0 | Addition |
| SUB | 1 | Subtraction |
| AND | 2 | Bitwise AND |
| OR | 3 | Bitwise OR |
| PASS | 4 | Pass-through input |

---

### Advantages

- Memory-mapped programming model
- No DMA required
- Simple software interface
- Straightforward debugging

---

# Design Tradeoffs & Summary

## Design Philosophy
- **Area-first:** Strict 0.25×0.25 mm die constraint requires minimal configurations and lightweight interconnect.
- **Simplicity:** Reduced instruction sets and operations for deterministic execution.
- **First-silicon:** Predictable signoff loops leveraging automated DRC/LVS/STA checks minimize tape-out risk.

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


# ChipOrchestra Design Flow

ChipOrchestra is an AI-orchestrated RTL-to-GDS design workflow driving the NanoCGRA SoC pipeline.

## Flow Pipeline
```mermaid
flowchart TB
    subgraph S01 [Stage 01: Ingest Spec]
        Spec[NL Spec] --> Manifest[Normalized Manifest]
    end
    subgraph S02 [Stage 02: Agent Plan]
        Manifest --> Plan[Runbook & Tool Configs <br/> OpenLane/GF180MCU]
    end
    subgraph S03 [Stage 03: Verify Loop]
        Plan --> RTL[RTL & TB Gen]
        RTL --> Sim[Verilator, Slang, SymbiYosys, OpenSTA]
        Sim -- Fail --> Plan
    end
    subgraph S04 [Stage 04: Implement]
        Sim -- Pass --> Synth[Yosys Synth & OpenROAD P&R]
        Synth --> Signoff[Magic DRC, Netgen LVS, OpenSTA]
    end
    subgraph S05 [Stage 05: Deliver]
        Signoff --> GDS[GDSII & Tapeout Package]
    end
    S01 --> S02 --> S03 --> S04 --> S05
```

## Benefits for NanoCGRA SoC
- ⚡ **Faster RTL iteration:** AI generates and refines RTL directly from specs.
- 🔄 **Automated Verify Loop:** Unified simulation & formal checks catch bugs early.
- 📐 **Area-aware Planning:** Selects minimal configs for the 0.25×0.25mm target.
- 🛠️ **Consistent Flow:** Ensures reliable OpenLane/GF180MCU execution.
- 🏅 **First-Silicon Confidence:** Automated DRC/LVS/STA signoff.

---

# Verification Plan

## Strategy
- **Unit Tests per Block:** Isolated testing for SRAM, UART, PE, and the SMPB bus.
- **Integration Simulation:** Verifying block interconnect and system-level operations.
- **Formal Checks:** Ensuring logical correctness of state machines and bus protocols.

## Toolchain
- **Simulation:** Verilator
- **Testbenches:** Cocotb / SystemVerilog TB
- **Formal Verification:** SymbiYosys
- **Static Timing Analysis:** OpenSTA

## Key Test Cases
1. **CGRA Configuration:** Write and readback validation for config registers.
2. **UART Loopback:** Ensuring serial transmit/receive fidelity.
3. **SRAM Read/Write:** Full address space integrity checks.
4. **Full SoC Smoke Test:** End-to-end execution combining CPU, bus, and CGRA operations.

*ChipOrchestra fully automates this loop, feeding failures back to the Agent Plan stage.*

---

# Implementation & Tapeout Plan

## Synthesis & Implementation
- **Synthesis:** Yosys targeting OpenLane flow for GF180MCU.
- **Place & Route (P&R):** OpenROAD focused on strict 0.25×0.25mm die area constraint.

## Signoff Procedures
- **DRC (Design Rule Check):** Magic
- **LVS (Layout vs. Schematic):** Netgen
- **Timing Closure:** OpenSTA

## Deliverables
- **GDSII:** Final layout generated via KLayout.
- **Signoff Reports:** Comprehensive documentation for DRC, LVS, and STA.
- **Tapeout Package:** Foundry-ready final assets.

## Risk Mitigations
- **Area Budget:** Constant monitoring during P&R to fit 0.25 mm².
- **Timing Closure:** Frequent STA checks throughout the flow.
- **First-silicon Checklist:** Strict adherence to automated verify and signoff loop.
