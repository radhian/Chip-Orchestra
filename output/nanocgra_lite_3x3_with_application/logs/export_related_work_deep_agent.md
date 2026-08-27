# Deep agent transcript — export_related_work_deep_agent

GOAL:
Find the PUBLISHED WORK this chip should be compared against, and write it as the single JSON file `exports/related_work.json`.

THE DESIGN: nano cgra 3x3 for sobel filter accelerator, i uploaded 2 images, 1 for you to understand the architecture of nano cgra what i want but for input output use UART, see it properly, and 1 for the reference image you build the sobel filter accelerator, uses 32x32 of that image, make sure the cropped image shows the road.
WHAT IT COMPUTES: The chip is a streaming 3x3 Sobel edge-detection accelerator. A 32x32 unsigned 8-bit pixel frame arrives over UART; two line buffers and a 3x3 window assembler form each 3x3 neighborhood, a 9-PE CGRA (plus a bit-exact combinational Sobel core) computes the horizontal and vertical gradients Gx and Gy, and the saturated gradient magnitude |Gx|+|Gy| is emitted as an unsigned 8-bit byte over UART for each of the 30x30 valid output positions. No full frame is buffered: every received pixel is shifted into the datapath and, once a valid window exists, the result is queued and transmitted immediately
MODULES ON THE CHIP: baud_gen, cgra_3x3, line_buffer, mmio_bus, nano_cgra_3x3_sobel_accelerator_v4, nano_controller, params, pe, reset_sync, sobel_core, sram_32b, uart_rx, uart_tx, window_3x3

CANDIDATE SOURCES — these URLs were already retrieved for this design; they are your starting point:
  - https://www.ijraset.com/research-paper/sobel-edge-detection-using-vlsi-on-fpga
  - https://ieeexplore.ieee.org/document/9516637
  - https://www.researchgate.net/publication/395987661_Comprehensive_RTL-to-GDSII_Workflow_for_Custom_Embedded_FPGA_Architectures_Using_Open-Source_Tools
  - https://arxiv.org/pdf/2405.04257
  - https://sebastianraschka.com/blog/2026/kimi-k3-architecture-notes.html
  - https://nanabananapro.com/
  - https://deepwiki.com/pnnl/OpenCGRA
  - https://www.easemate.ai/nano-banana-ai-image-generator
  - https://nano-banana2.com/
  - https://yt2song.com/
  - https://videocompress.ai/image-translator
  - https://imagegpt2.com/

METHOD:
  1. Call fetch_reference on the candidates that look relevant to the algorithm, the datapath style, the host interface, or the open-source tapeout flow. The fetched text is what you cite from — read the real title, authors and venue out of it.
  2. Discard anything that turns out to be unrelated or is not a real publication or primary project page.
  3. WRITE THE FILE as soon as you have 4 usable entries. Do not keep hunting for a better bibliography — an incomplete related-work section is fine, an export that never finishes is not.
  4. `search_web` returns a written summary of a topic, NOT a list of papers, so it cannot give you a citation. Use it at most twice, only to understand a topic well enough to describe how a fetched reference relates to this design.

SCHEMA: {"summary": "3-5 sentences positioning THIS design against that work — what has been done before, and what is different here (an AI-generated, golden-model-gated implementation on an open PDK)", "references": [{"authors": "A. Author and B. Author", "title": "Paper title", "venue": "Conference or journal, year", "year": "2021", "url": "https://...", "relation": "one sentence on how it relates to this design"}]}

HARD RULES — this goes into a formal paper, so a fabricated citation is worse than no citation:
  - EVERY entry must come from a page you ACTUALLY fetched. Put that exact URL in "url". Never cite a candidate you did not open.
  - Never invent a DOI, a page range, or an author list you did not read. If you only know the title and the venue, give those and leave the rest out.
  - If you cannot verify a claim about a paper, do not make it.
  - 4 to 8 references. Prefer peer-reviewed work; a well-known technical report or an official project page is acceptable when it is the primary source.

Write the file with write_file_disk and reply 'done'.


**tool call:** `read_file_disk` {'path': 'context/state.md'}

**tool call:** `list_files` {}

> tool result: # context/state.md — 37 lines, 6275 chars; showing 1-37
# context/state.md — Run journal

Every stage appends here; deep agents read this FIRST.

- **2026-08-15 03:11 · spec_ingest:done** — brief captured; attachments=['Screenshot_from_2026-07-14_16-24-31.png', 'Screenshot_from_2026-08-01_19-42-51.png']; vision digest at context/uploads_digest.md
- **2026-08-15 03:25 · planning:done** — Grand plan written. Architecture: 3×3 CGRA (9 PEs) + NanoController FSM + MMIO bus + 32B SRAM + UART I/O, streaming Sobel on 32×32 image. Top module: nano_cgra_3x3_sobel_accelerator_v4. 14 RTL files planned. Input crop: (20,340) 32×32 from highway image showing road. References studied: stffrdhrn/uart, 123-code/cnn_chip, pnnl/OpenCGRA. Plan at plans/execution_plan.md, contract at context/design_notes.md. Ar

> tool result: .pytest_cache/.gitignore
.pytest_cache/CACHEDIR.TAG
.pytest_cache/README.md
.pytest_cache/v/cache/lastfailed
.pytest_cache/v/cache/nodeids
.pytest_cache/v/cache/stepwise
context/achieved_clock.json
context/anchor/Pacman-TangNano9k/efinix_hdmi_audio_info_frame.sv
context/anchor/Pacman-TangNano9k/efinix_hdmi_hdmi.sv
context/anchor/Pacman-TangNano9k/efinix_hdmi_packet_assembler.sv
context/anchor/Pacman-TangNano9k/efinix_hdmi_packet_picker.sv
context/anchor/Pacman-TangNano9k/efinix_hdmi_serializer.sv
context/anchor/Pacman-TangNano9k/efinix_hdmi_tmds_channel.sv
context/anchor/Pacman-TangNano9k/efinix_roms_pacman_5e.v
context/anchor/Pacman-TangNano9k/efinix_roms_pacman_5f.v
context/anchor/Pacman-TangNano9k/efinix_roms_pacman_6e.v
context/anchor/Pacman-TangNano9k/efinix_roms_pacman_6f.v
context/a

**assistant:** I'll start by checking the already-fetched OpenCGRA reference and the sources file, then fetch the most relevant candidates.

**tool call:** `read_file_disk` {'path': 'context/sources.md'}

**tool call:** `read_file_disk` {'path': 'context/refs/https___deepwiki_com_pnnl_OpenCGRA.md', 'max_lines': 60}

> tool result: # context/sources.md — 17 lines, 674 chars; showing 1-17
# Reference sources (gathered from the web)

## HDL repositories
- https://github.com/harbaum/Pacman-TangNano9k
- https://github.com/cassuto/nano-cpu32k
- https://github.com/nhasbun/de10nano_vgaHdmi_chip
- https://github.com/123-code/gpu_design
- https://github.com/stffrdhrn/uart
- https://github.com/123-code/cnn_chip

## Papers / articles
- https://www.ijraset.com/research-paper/sobel-edge-detection-using-vlsi-on-fpga
- https://www.slideshare.net/slideshow/09-accelerators/250289162
- https://sebastianraschka.com/blog/2026/kimi-k3-architecture-notes.html
- https://nanabananapro.com/
- https://deepwiki.com/pnnl/OpenCGRA
- https://ieeexplore.ieee.org/document/9516637

> tool result: # context/refs/https___deepwiki_com_pnnl_OpenCGRA.md — 248 lines, 7342 chars; showing 1-60
pnnl/OpenCGRA | DeepWiki
Loading...

Index your code with Devin
DeepWiki DeepWiki pnnl/OpenCGRA

Index your code with

Devin
Edit Wiki Share

Loading...

Last indexed: 3 May 2025 ( 2526bd )

OpenCGRA Overview
Installation and Setup
CGRA Architecture
Tile Structure
Functional Units
Basic Functional Units
Composite Functional Units
Control System
Memory System
Data Flow Graphs
Operations and Messages
Systolic Array Implementation
Testing and Verification
Advanced Configuration

Menu

OpenCGRA Overview

Relevant source files

.gitignore

.travis.yml

README.md

codecov.yml

OpenCGRA is a parameterizable and powerful Coarse-Grained Reconfigurable Arrays (CGRA) generator that produces synthesizable Verilo

**assistant:** I have the OpenCGRA reference. Now let me fetch the most relevant candidates: the Sobel VLSI paper, the IEEE document, the RTL-to-GDSII workflow paper, and the arxiv paper.

**tool call:** `fetch_reference` {'url': 'https://www.ijraset.com/research-paper/sobel-edge-detection-using-vlsi-on-fpga'}

**tool call:** `fetch_reference` {'url': 'https://ieeexplore.ieee.org/document/9516637'}

**tool call:** `fetch_reference` {'url': 'https://www.researchgate.net/publication/395987661_Comprehensive_RTL-to-GDSII_Workflow_for_Custom_Embedded_FPGA_Architectures_Using_Open-Source_Tools'}

**tool call:** `fetch_reference` {'url': 'https://arxiv.org/pdf/2405.04257'}

> tool result: Saved to context/refs/t_com_research_paper_sobel_edge_detection_using_vlsi_on_fpga.md.

Designing SOBEL Edge Detection Using VLSI on FPGA

-->

-->

-->

-->

-->

-->
-->

-->

-->
-->
-->

-->
-->
-->

-->

Ijraset Journal For Research in Applied Science and Engineering Technology

Home / Ijraset

On This Page

Abstract

Introduction

Conclusion

References

Copyright

Designing SOBEL Edge Detection Using VLSI on FPGA

Authors: A. Vani , D SathyaNarayana, G Anirudh, Y Nikhil

DOI Link: https://doi.org/10.22214/ijraset.2025.72009

Certificate:
View Certificate

Abstract

Edge detection is a critical operation in image processing, widely used in fields such as computer vision, robotics, medical imaging, and object recognition. The Sobel operator, known for its simplicity and effectiveness,

> tool result: (nothing usable at https://ieeexplore.ieee.org/document/9516637)

> tool result: (nothing usable at https://www.researchgate.net/publication/395987661_Comprehensive_RTL-to-GDSII_Workflow_for_Custom_Embedded_FPGA_Architectures_Using_Open-Source_Tools)

> tool result: (nothing usable at https://arxiv.org/pdf/2405.04257)

**assistant:** I have the Sobel VLSI paper. The IEEE, ResearchGate, and arxiv fetches failed. Let me try the OpenCGRA deepwiki page (already fetched) and search the web for the arxiv paper and the RTL-to-GDSII paper to understand them better, and try fetching the arxiv abstract page instead.

**tool call:** `search_web` {'query': 'arxiv 2405.04257 paper title authors'}

**tool call:** `search_web` {'query': 'Comprehensive RTL-to-GDSII Workflow Custom Embedded FPGA Architectures Open-Source Tools paper authors venue'}

> tool result: WEB KNOWLEDGE for 'arxiv 2405.04257 paper title authors':
**WHAT:** mPLUG-Owl2 (arXiv:2311.04257) is a Multi-modal Large Language Model (MLLM) architecture. It processes text and images using a modularized design where a shared language decoder acts as a universal interface, augmented by modality-adaptive modules to preserve modality-specific features while enabling cross-modality collaboration.

**HOW (RTL Implementation):**
*Architecture:* Maps to a heterogeneous AI accelerator SoC. A Vision Encoder (e.g., ViT) processes images into visual tokens, which are projected into the LLM's embedding space. A shared Transformer Engine then processes the unified token stream.
*Key Modules & Interfaces:*
- Vision Encoder: Input = pixel arrays; Output = visual feature vectors.
- Projection Block: Al

> tool result: WEB KNOWLEDGE for 'Comprehensive RTL-to-GDSII Workflow Custom Embedded FPGA Architectures Open-Source Tools paper authors venue':
*The provided web result is a generic LinkedIn post on FPGA skills, lacking specific paper details. Based on standard knowledge of this topic:*

**WHAT:** A comprehensive RTL-to-GDSII workflow for custom embedded FPGAs (eFPGAs) generates a reconfigurable fabric and takes it through physical implementation using open-source EDA tools (e.g., OpenFPGA, Yosys, VTR, OpenLANE). It enables integrating customizable FPGA blocks into ASICs/SoCs.

**Architecture & Key Modules:** The RTL typically defines a grid of Configurable Logic Blocks (CLBs) containing LUTs and flip-flops, Routing Blocks (Switch Boxes and Connection Boxes), I/O blocks, and optional hard IPs (BRAMs, DS

**assistant:** The arxiv paper turned out to be about a multimodal LLM (unrelated), and the IEEE/ResearchGate fetches failed. Let me read the already-fetched reference files and try the arxiv abstract page.

**tool call:** `read_file_disk` {'max_lines': 40, 'path': 'context/refs/https___github_com_stffrdhrn_uart.v'}

**tool call:** `read_file_disk` {'max_lines': 40, 'path': 'context/refs/https___github_com_123_code_cnn_chip.v'}

**tool call:** `read_file_disk` {'path': 'context/refs/https___deepwiki_com_pnnl_OpenCGRA.md', 'start_line': 61, 'max_lines': 80}

**tool call:** `fetch_reference` {'url': 'https://arxiv.org/abs/2405.04257'}

> tool result: # context/refs/https___github_com_stffrdhrn_uart.v — 353 lines, 9000 chars; showing 1-40
// ===== uart/rtl/rx.v =====
/* UART Receiver module 
 * Receives the serial signal on the rx pin.  Uses 4 posedge's
 * per baud bit to detect when the start bit comes.  Then every
 * 4 bits after that we shift in a sample to read our byte. 
 * Sets rdy output high after the byte is ready successfully. 
 *
 * Note, we dont really check that the stop bit goes high. 
 *
 * Has asynchronous reset. 
 */ 
module rx (
  input         res_n,
  input         rx,
  input         clk, /* Baud Rate x 4 (4 posedge's per bit) */
  output  [7:0] rx_byte,
  output        rdy
);

/* Count to 32 (8 bits x 4 samples )*/
reg       [4:0] count;
reg       [2:0] state;
reg       [2:0] state_nxt;

reg       [2:0] rx_shifter;

> tool result: # context/refs/https___github_com_123_code_cnn_chip.v — 289 lines, 9000 chars; showing 1-40
// ===== cnn_chip/uart_rx.v =====
module uart_rx #(
    parameter CLK_FREQ = 27000000,
    parameter BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx_in,
    output reg  [7:0] rx_byte,
    output reg        rx_valid
);

    localparam BIT_TICK = CLK_FREQ / BAUD_RATE;
    localparam HALF_TICK = BIT_TICK / 2;

    localparam IDLE  = 2'b00;
    localparam START = 2'b01;
    localparam DATA  = 2'b10;
    localparam STOP  = 2'b11;

    reg [1:0] state;
    reg [15:0] tick_counter;
    reg [2:0] bit_index;
    reg [7:0] shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            tick_cou

> tool result: # context/refs/https___deepwiki_com_pnnl_OpenCGRA.md — 248 lines, 7342 chars; showing 61-140
The framework is designed to support both research exploration and industrial application by offering a high degree of customization while maintaining hardware implementability.

Sources: README.md 13-14

High-Level Architecture

OpenCGRA is organized into several key subsystems that work together to define, configure, and execute computations on a CGRA.

System Architecture Overview

The diagram shows the main components of OpenCGRA:

Data Flow Graph (DFG) : Represents computations to be executed on the CGRA

Control System : Translates DFGs into configuration information

CGRARTL : The core hardware description containing the configurable CGRA

Functional Units : Computational elements that perfo

> tool result: Saved to context/refs/https___arxiv_org_abs_2405_04257.md.

[2405.04257] Insights from Basilisk: Are Open-Source EDA Tools Ready for a Multi-Million-Gate, Linux-Booting RV64 SoC Design?

Skip to main content

Search arXiv

Press Enter to search &middot; Advanced search

-->

Computer Science > Hardware Architecture

arXiv:2405.04257 (cs)

[Submitted on 7 May 2024 ( v1 ), last revised 8 May 2024 (this version, v2)]

Title: Insights from Basilisk: Are Open-Source EDA Tools Ready for a Multi-Million-Gate, Linux-Booting RV64 SoC Design?

Authors: Philippe Sauter , Thomas Benz , Paul Scheffler , Frank K. Gürkaynak , Luca Benini
View a PDF of the paper titled Insights from Basilisk: Are Open-Source EDA Tools Ready for a Multi-Million-Gate, Linux-Booting RV64 SoC Design?, by Philippe Sauter and 4

**assistant:** I now have 5 solid fetched references. Let me quickly check the cnn_chip reference to describe it accurately.

**tool call:** `read_file_disk` {'max_lines': 30, 'path': 'context/refs/https___github_com_123_code_cnn_chip.v', 'start_line': 41}

> tool result: # context/refs/https___github_com_123_code_cnn_chip.v — 289 lines, 9000 chars; showing 41-70
                        tick_counter <= 0;
                    end
                end
                
                START: begin
                    if (tick_counter == HALF_TICK) begin
                        if (rx_in == 1'b0) begin // Confirm it's still 0
                            state <= DATA;
                            tick_counter <= 0;
                            bit_index <= 0;
                        end else begin
                            state <= IDLE; // False alarm
                        end
                    end else begin
                        tick_counter <= tick_counter + 1;
                    end
                end
                
                DATA: begin
   

**tool call:** `grep_files` {'pattern': 'module |cnn|conv|sobel|kernel|pe|cgra', 'subdir': 'context/refs'}

> tool result: context/refs/https___arxiv_org_abs_2405_04257.md:1: [2405.04257] Insights from Basilisk: Are Open-Source EDA Tools Ready for a Multi-Million-Gate, Linux-Booting RV64 SoC Design?
context/refs/https___arxiv_org_abs_2405_04257.md:17: Title: Insights from Basilisk: Are Open-Source EDA Tools Ready for a Multi-Million-Gate, Linux-Booting RV64 SoC Design?
context/refs/https___arxiv_org_abs_2405_04257.md:19: Authors: Philippe Sauter , Thomas Benz , Paul Scheffler , Frank K. Gürkaynak , Luca Benini
context/refs/https___arxiv_org_abs_2405_04257.md:20: View a PDF of the paper titled Insights from Basilisk: Are Open-Source EDA Tools Ready for a Multi-Million-Gate, Linux-Booting RV64 SoC Design?, by Philippe Sau
context/refs/https___arxiv_org_abs_2405_04257.md:23: HTML (experimental)
context/refs/https

**tool call:** `read_file_disk` {'max_lines': 20, 'path': 'context/refs/https___deepwiki_com_pnnl_OpenCGRA.md', 'start_line': 195}

> tool result: # context/refs/https___deepwiki_com_pnnl_OpenCGRA.md — 248 lines, 7342 chars; showing 195-214
Related Research

OpenCGRA has been used in several research publications:

&quot;AURORA: Automated Refinement of Coarse-Grained Reconfigurable Accelerators&quot; (DATE-21)

&quot;ARENA: Asynchronous Reconfigurable Accelerator Ring to Enable Data-Centric Parallel Computing&quot; (TPDS-21)

&quot;OpenCGRA: An Open-Source Framework for Modeling, Testing, and Evaluating CGRAs&quot; (ICCD-20)

These publications demonstrate applications and extensions of the OpenCGRA framework in various domains.

Sources: README.md 21-25

Further Documentation

For more detailed information on specific aspects of OpenCGRA, please refer to:

CGRA Architecture - Detailed architecture description

… (34 more lines — rea

**assistant:** I have 5 solid fetched references. Let me write the JSON file now.

**tool call:** `write_file_disk` {'path': 'exports/related_work.json', 'content': {'summary': 'Streaming Sobel edge-detection accelerators with 3x3 line-buffer/window datapaths have been demonstrated on FPGAs in Verilog HDL, establishing the canonical algorithm-to-hardware mapping this chip follows. Coarse-grained reconfigurable arrays (CGRAs) as a compute substrate have been formalized by open-source frameworks such as OpenCGRA,

> tool result: Error: 1 validation error for write_file_disk
content
  Input should be a valid string [type=string_type, input_value={'summary': 'Streaming So...gradient magnitudes.'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.10/v/string_type
 Please fix your mistakes.

**tool call:** `write_file_disk` {'path': 'exports/related_work.json', 'content': {'summary': 'Streaming Sobel edge-detection accelerators with 3x3 line-buffer/window datapaths have been demonstrated on FPGAs in Verilog HDL, establishing the canonical algorithm-to-hardware mapping this chip follows. Coarse-grained reconfigurable arrays (CGRAs) as a compute substrate have been formalized by open-source frameworks such as OpenCGRA,

> tool result: Error: 1 validation error for write_file_disk
content
  Input should be a valid string [type=string_type, input_value={'summary': 'Streaming So...gradient magnitudes.'}]}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.10/v/string_type
 Please fix your mistakes.

**tool call:** `run_python` {'code': 'import json\ndata = {\n  "summary": "Streaming Sobel edge-detection accelerators with 3x3 line-buffer/window datapaths have been demonstrated on FPGAs in Verilog HDL, establishing the canonical algorithm-to-hardware mapping this chip follows. Coarse-grained reconfigurable arrays (CGRAs) as a compute substrate have been formalized by open-source frameworks such as OpenCGRA, which generate

> tool result: [OK]
written

**assistant:** done