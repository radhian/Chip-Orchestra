# Design Brief — nano cgra 3x3 sobel accelerator v4

nano cgra 3x3 for sobel filter accelerator, i uploaded 2 images, 1 for you to understand the architecture of nano cgra what i want but for input output use UART, see it properly, and 1 for the reference image you build the sobel filter accelerator, uses 32x32 of that image, make sure the cropped image shows the road.

## Interfaces
- `clk`
- `rst_n`
- `data_i`
- `data_o`

## Assumptions
- Single clock domain
- Synchronous active-low reset

## Risks
- Unspecified timing budget
- Testbench coverage may be partial

## Attached files
- `Screenshot_from_2026-07-14_16-24-31.png`
- `Screenshot_from_2026-08-01_19-42-51.png`

The attachment digest (vision model reading of images, extracted PDF text) is at `context/uploads_digest.md`.
