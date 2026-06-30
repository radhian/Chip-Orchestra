# RTL Design Guidelines

Language

Verilog-2001

Naming

Modules

snake_case

Example

uart_top

Signals

lower_case

Parameters

UPPER_CASE

Reset

Active Low

Combinational Logic

always @(*)

Sequential Logic

always @(posedge clk)

No inferred latches.

No tri-state logic.

Fully synthesizable.