import json
data = {
  "summary": "Streaming Sobel edge-detection accelerators with 3x3 line-buffer/window datapaths have been demonstrated on FPGAs in Verilog HDL, establishing the canonical algorithm-to-hardware mapping this chip follows. Coarse-grained reconfigurable arrays (CGRAs) as a compute substrate have been formalized by open-source frameworks such as OpenCGRA, which generate parameterizable tile grids of functional units; this design instantiates a small, fixed 3x3 CGRA rather than a general reconfigurable fabric. Open-source EDA flows and open PDKs have matured enough for full tapeout, as proven by the Basilisk RV64 SoC in IHP 130 nm, validating the open-source RTL-to-GDSII path used here. The UART-based streaming host interface follows well-known open UART cores and compact CNN-accelerator SoCs that feed pixel data over UART. The differentiator of this work is that it is an AI-generated, golden-model-gated implementation of a 3x3 CGRA Sobel accelerator targeting an open PDK, combining the streaming line-buffer Sobel datapath, a fixed CGRA PE array, and UART I/O in a single taped-out chip.",
  "references": [
    {
      "authors": "A. Vani, D. SathyaNarayana, G. Anirudh, Y. Nikhil",
      "title": "Designing SOBEL Edge Detection Using VLSI on FPGA",
      "venue": "IJRASET, 2025",
      "year": "2025",
      "url": "https://www.ijraset.com/research-paper/sobel-edge-detection-using-vlsi-on-fpga",
      "relation": "Implements the same 3x3 Sobel convolution with line buffering and windowing in Verilog HDL on an FPGA; this chip follows the same algorithmic datapath but targets an ASIC CGRA with UART streaming I/O."
    },
    {
      "authors": "OpenCGRA Project (Pacific Northwest National Laboratory)",
      "title": "OpenCGRA: An Open-Source Framework for Modeling, Testing, and Evaluating CGRAs",
      "venue": "ICCD 2020; project documentation at DeepWiki",
      "year": "2020",
      "url": "https://deepwiki.com/pnnl/OpenCGRA",
      "relation": "Defines a parameterizable CGRA generator producing synthesizable Verilog tile grids of functional units; this design uses a small fixed 3x3 CGRA inspired by that tile-based architecture."
    },
    {
      "authors": "P. Sauter, T. Benz, P. Scheffler, F. K. Gürkaynak, L. Benini",
      "title": "Insights from Basilisk: Are Open-Source EDA Tools Ready for a Multi-Million-Gate, Linux-Booting RV64 SoC Design?",
      "venue": "IWLS 2024",
      "year": "2024",
      "url": "https://arxiv.org/abs/2405.04257",
      "relation": "Demonstrates a full open-source Yosys+OpenROAD EDA flow taped out in IHP's open 130 nm PDK, establishing the viability of the open-source RTL-to-GDSII path this chip also uses."
    },
    {
      "authors": "stffrdhrn",
      "title": "uart: Compact open-source UART RX/TX cores in Verilog",
      "venue": "GitHub repository",
      "year": "2020",
      "url": "https://github.com/stffrdhrn/uart",
      "relation": "Provides the reference baud-sampled UART receive/transmit architecture that this chip's uart_rx and uart_tx modules are modeled on for streaming pixel I/O."
    },
    {
      "authors": "123-code",
      "title": "cnn_chip: Compact CNN accelerator SoC with UART streaming I/O",
      "venue": "GitHub repository",
      "year": "2023",
      "url": "https://github.com/123-code/cnn_chip",
      "relation": "A small accelerator SoC that streams data over UART into a Verilog datapath, mirroring the host-interface style this Sobel accelerator uses to receive pixels and emit gradient magnitudes."
    }
  ]
}
with open('exports/related_work.json', 'w') as f:
    json.dump(data, f, indent=2)
print("written")