# GF180 Chipathon Workshop — timing constraints
#
# The clock enters through input pad pad_w_in_0: the external "clk" port drives
# the pad PAD pin, and the pad's Y pin drives the on-chip clock net (clk_core).
# The pad is a blackbox with no liberty, so the clock cannot propagate through
# it in STA — define the clock on the core side (the pad Y pin) so CTS builds a
# real tree to the core flip-flops.
create_clock -name clk -period 100.0 [get_pins pad_w_in_0/Y]
set_clock_uncertainty 0.25 [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]
