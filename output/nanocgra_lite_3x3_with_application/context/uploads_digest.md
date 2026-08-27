# User-attached files (uploaded with the task)

### Screenshot_from_2026-07-14_16-24-31.png (image · DATA)
Saved at `context/uploads/Screenshot_from_2026-07-14_16-24-31.png`. ROLE: CHIP INPUT DATA — the finished chip must PROCESS this content. Do NOT derive modules from its shapes. At testbench time, preprocess THIS file with run_python (PIL/numpy) into the chip's input format (rtl/<name>.mem via $readmemh) and visualize it to waves/chip_input.png.
To describe the provided highway scene as **INPUT DATA** for a hardware accelerator (e.g., in an autonomous vehicle or traffic monitoring system), we must structure the description with precision: spatial layout, pixel/coordinate semantics, color/value meaning, and computational objectives.

---

## 🖼️ IMAGE CONTENT DESCRIPTION

The image depicts a multi-lane highway under clear daylight conditions. Key elements include:

- **Road surface**: Asphalt road with white dashed lane dividers (left lanes) and solid right-edge line.
- **Vehicles**: 
  - Red SUV on far left lane (closest to camera).
  - Black sedan in center-left lane ahead.
  - White car in center-right lane further ahead.
  - Additional distant vehicles visible.
- **Environment**: Dry grassy embankment on right, trees and hills in background, blue sky above.

---

## 📐 GRID / PIXEL STRUCTURE & DIMENSIONS

Assume standard input resolution for hardware accelerators:

> **Resolution**: `1920 × 1080` pixels (Full HD)  
> **Color Depth**: 8-bit per channel → RGB values in range `[0, 255]`  
> **Coordinate System**: Origin at top-left; x increases rightward, y downward.

### Lane Geometry Approximation:
- Road occupies bottom ~70% of frame (y > 360).
- Leftmost lane boundary ≈ x=0 to x≈480 (red SUV in this region).
- Center lanes span x≈500–1200.
- Right shoulder/embankment: x>1200, y>700.

### Vehicle Bounding Boxes (Approximate):

| Object        | Approx Coordinates       | Notes                          |
|---------------|--------------------------|--------------------------------|
| Red SUV       | [0, 540] to [96, 680]   | Leftmost lane                 |
| Black Car     | [312, 557] to [350, 605]| Center-left lane              |
| White Car     | [426, 563] to [459, 589]| Center-right lane             |

*(Note: These are approximate bounding boxes based on visual estimation — actual detection would require algorithmic processing.)*

---

## 🎨 COLOR / VALUE MEANING & SEMANTIC INTERPRETATION

Hardware accelerators often use color thresholds or semantic segmentation masks to extract meaningful data:

### Road Surface (Asphalt):
- **RGB Range**: ~[30, 50] in all channels → dark gray/black.
- Used for lane detection via edge/gradient analysis.

### Lane Markings:
- **White Dashed Lines**: High reflectivity → RGB ≈ [240–255], high contrast against asphalt.
- Detected using Sobel filters or Hough transforms on grayscale/intensity maps.

### Vehicles:
- **Red SUV**: R > G, B; saturation > 100 → red channel dominant.
- **Black Car**: Low intensity across all channels (<60).
- **White Car**: High intensity (~240+) in all channels.

### Sky & Background:
- **Sky**: Blue tones — B ≈ R+G, e.g., [50, 180] → used for horizon detection or sky segmentation if needed.
- **Trees/Hills**: Green/brown hues — G > R,B; useful for vegetation masking.

### Embankment (Right Side):
- Dry grass: Yellow-brown tones — R≈G>B, medium intensity (~[150–200]).

---

## ⚙️ COMPUTATIONAL OBJECTIVES FOR HARDWARE ACCELERATOR

A chip processing this input would compute the following tasks in parallel pipelines or tensor cores:

### 1. **Lane Detection & Tracking**
- Input: Raw RGB image + optional depth (if stereo/LiDAR fused).
- Compute: 
  - Edge gradients → Sobel filter output.
  - Hough transform parameters for straight lines.
  - Output: Lane centerline coordinates per frame, curvature rate.

### 2. **Object Detection & Classification**
- Input: ROI crops from detected bounding boxes or full image.
- Compute: 
  - CNN inference (e.g., YOLOv8, Faster R-CNN) → class probabilities + confidence scores.
  - Output: List of objects with {x,y,w,h,class_id,score}.

### 3. **Speed Estimation**
- Input: Consecutive frames over time Δt.
- Compute: 
  - Optical flow or feature tracking (e.g., KLT algorithm).
  - Distance traveled / dt → speed estimate in m/s.

### 4. **Traffic Density & Flow Analysis**
- Input: Detected vehicle positions across lanes and time windows.
- Compute: 
  - Vehicles per kilometer per lane.
  - Average gap between vehicles.
  - Output: Traffic state vector (free-flow, congested, etc.).

### 5. **Safety Margin Calculation**
- Input: Own ego-vehicle position + relative speeds of surrounding cars.
- Compute: Time-to-collision (TTC) for each nearby vehicle using kinematic equations.

---

## 🔧 HARDWARE ACCELERATOR SPECIFICATIONS (Example)

For real-time processing at 30 FPS on edge device:

| Component             | Specification                     | Purpose                          |
|-----------------------|----------------------------------|----------------------------------|
| GPU / NPU Core        | NVIDIA Jetson Orin NX            | Parallel CNN inference           |
| Memory Bandwidth      | ≥1 TB/s (HBM2e)                  | Feed forward/backward tensors    |
| Tensor Cores          | FP16/INT8 support                | Accelerate matrix multiplications|
| Latency Target        | <5 ms per frame                  | Real-time control loop           |

---

## ✅ SUMMARY OUTPUT FORMAT (for downstream systems)

```json
{
  "frame_id": 42,
  "timestamp_ms": 1738900000,
  "detected_objects": [
    {
      "bbox_2d": {"x_min": 0, "y_min": 540, "x_max": 96, "y_max": 680},
      "class_id": "car",
      "confidence": 0.97,
      "color_profile": { "r_mean": 120, "g_mean": 30, "b_mean": 40 }
    },
    ...
  ],
  "lane_centers": [ {"x": 85}, {"x": 620}, {"x": 970} ], // relative to image width
  "ego_speed_estimated_mps": 31.5,
  "traffic_density_vpk": { "left_lane": 45, "center_left": 38, "center_right": 36 },
  "safety_alerts": [] 
}
```

---

This structured representation enables efficient mapping to hardware accelerator pipelines — leveraging parallelism for detection, low-latency inference for safety-critical decisions, and precise coordinate/color semantics for accurate environmental modeling.
Open the image with run_python (PIL) only if you need a finer detail.

### Screenshot_from_2026-08-01_19-42-51.png (image · ARCHITECTURE)
Saved at `context/uploads/Screenshot_from_2026-08-01_19-42-51.png`. ROLE: ARCHITECTURE — this is the build spec. Construct the RTL module map to match this diagram's blocks, connections, and widths. Do NOT feed this image into the chip as data.
Based on the provided schematic review video slide for "System Architecture and Architecture Integration," here is a precise structural description of every block/module with its exact label, bit-widths (where shown), signal names, connections between blocks, buses, clocks, resets, interfaces:

---

### **Top-Level System Blocks & Interfaces**
- **Host (PC / MCU)**  
  - Interface: UART (2-wire) → connects to system via RX/TX lines.
  - Signals: TX (transmit), RX (receive). Width = 1 bit each; direction bidirectional over serial link.

- **NanoController (microcoded FSM)** — Master Controller Block  
  Sub-blocks inside green box labeled “NANO CONTROLLER (FSM SEQUENCER)”:
    - UART Command Decoder → outputs control signals to MMIO Master and internal logic.
    - Configuration Registers → memory-mapped registers for config; accessed via bus.
    - Address Generator → generates addresses for SRAM/CGRA access; connected internally to FSM sequencer.
    - Loop Counter → counts iterations in microcode loop; tied to Sequencer FSM.
    - Sequencer FSM → state machine driving control flow; outputs enable signals to CGRA and other slaves.
    - Status Logic → monitors system status (e.g., done, busy); drives STATUS/CTRL register bits.
    - MMIO Master → master interface for memory-mapped I/O; connects to 8-bit bus as sole initiator.

- **3×3 CGRA Accelerator** — Main Compute Engine Block  
  Sub-blocks inside blue box labeled “3×3 CGRA ACCELERATOR (Main Compute Engine)”:
    - PE0–PE8: Nine Processing Elements, each an 8-bit MAC unit.
      - Each PE has internal data paths and control inputs/outputs to neighbors or I/F ports.
      - Interconnects between PEs form a mesh-like topology with bidirectional arrows indicating operand/data flow.
    - N/I/F (North Interface) → connects top row of PEs upward; likely for external input/output or chaining.
    - W/I/F (West Interface) → left-side interface; may connect to host or another accelerator.
    - E/I/F (East Interface) → right-side interface; similar function as West but opposite direction.
    - S/I/F (South Interface) → bottom interface; connects downward to SRAM via lightweight MMIO interconnect.

- **Lightweight MMIO Interconnect (8-bit)** — Central Bus Fabric  
  Label: “LIGHTWEIGHT MMIO INTERCONNECT (8-bit)” with sub-label “(Simple Address Decoder)”
    - Connects all slave devices: SRAM, UART, Reset Logic.
    - Driven by NanoController’s MMIO Master; acts as single shared address/data fabric.
    - Width = 8 bits for data/address lines.

- **SRAM (Macro)** — Operand + Result Storage  
  Label: “SRAM (Macro)”, size noted as “32 B (256-bit total)” with note “Single Port”.
    - Internal grid shows bit positions b7–b0 across rows from 0x00 to 0x1F.
    - Connected via bidirectional arrow to MMIO Interconnect; supports read/write operations.

- **UART (Memory Mapped)** — Off-chip I/O Block  
  Label: “UART (Memory Mapped)” with sub-blocks:
    - TX → transmit register/output port.
    - RX → receive input buffer/register.
    - STATUS/CTRL → status/control registers; mapped to specific addresses.
    - BAUD GEN (Baud Rate Generator) — generates clock for UART timing; internal component not directly interfaced externally beyond standard UART pins.

- **RESET LOGIC**  
  Label: “RESET LOGIC” with sub-labels:
    - Power-On Reset → active-low reset signal generated on power-up.
    - Sync Reset Gen → synchronous reset generation logic (likely clocked).
    - Outputs reset signals to all major blocks via dedicated lines (not explicitly named but implied by block boundaries).

---

### **Block Checklist Table Summary**
| Block                          | Inst.   | Bus Role     | Verified       |
|--------------------------------|---------|--------------|----------------|
| NanoController (FSM)           | ✓       | master       | GLS            |
| uart_bridge (sole master)      | ✓       | master       | RTL+GLS        |
| 3×3 CGRA (9 PEs)               | ✓       | slave        | RTL+GLS        |
| 32 B SRAM                      | ✓       | slave        | RTL+GLS        |
| UART TX/RX                     | ✓       | slave        | RTL+GLS        |
| Address decoder                | ✓       | fabric       | RTL            |
| 4-pin top-level I/O            | ✓       | —            | layout (4 pins)|

> Note: “Inst.” column indicates implementation status; “Verified” shows verification method (RTL = Register Transfer Level, GLS = Gate-Level Simulation).

---

### **Address Decoder (8-Bit Map) Table**
| Address Range   | Region                     | Size  | Acc.     |
|------------------|----------------------------|-------|----------|
| 0x00 – 0x1F      | SRAM data                  | 32 B  | R/W      |
| 0x80 – 0x83      | UART regs (TXDATA/RXDATA/STATUS/CTRL) | 4 B   | R/W      |
| 0x90 – 0x98      | CGRA config (cfg0..cfg8, 9 PEs) | 9 B   | R/W      |
| 0x99 – 0x9B      | CGRA operands (opa/opb/res addr) | 3 B   | R/W      |
| 0xA0             | START (kick CGRA run)      | 1 B   | W        |
| 0xA1             | STATUS {6'b0, done, busy}  | 1 B   | R        |

> Memory map note: “8-bit address space, 256 locations; driven by the uart_bridge over the internal bus.”

---

### **Interfaces & Connections Summary**
- **UART Bridge**: Acts as sole master on external UART (Host ↔ System); maps to internal MMIO interconnect.
- **MMIO Interconnect**: Single 8-bit bidirectional fabric connecting:
    - NanoController (as initiator)
    - SRAM (slave, read/write)
    - UART TX/RX registers (slaves)
    - CGRA configuration/status ports (via address decoder mapping)
- **Reset Signals**: Generated by Reset Logic block; distributed to all major blocks (implied via gray box connections).
- **Clocks/Clocks Not Explicitly Shown**: No clock signals labeled in diagram — assumed internal or derived from UART baud gen.
- **Data Paths Between PEs**: Bidirectional arrows between adjacent PE0–PE8 indicate operand/data exchange within CGRA compute engine.

---

### 
Open the image with run_python (PIL) only if you need a finer detail.