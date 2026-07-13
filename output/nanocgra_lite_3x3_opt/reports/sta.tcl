#==============================================================================
# Post-route STA report for NanoCGRA_Lite OPT 3x3 (9 PE / 32B / 4-pin UART)
#==============================================================================
set SCDIR $::env(PDK_ROOT)/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
read_liberty $SCDIR/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib
read_db output/nanocgra_lite_3x3_opt/pnr/nanocgra_lite_3x3_opt.odb

create_clock -name clk -period 100.0 [get_ports clk]
set_input_delay  20.0 -clock clk [all_inputs]
set_output_delay 20.0 -clock clk [all_outputs]
set_propagated_clock [all_clocks]

set_wire_rc -signal -layer Metal3
set_wire_rc -clock  -layer Metal4
estimate_parasitics -placement

puts "=================================================================="
puts "  NanoCGRA_Lite OPT 3x3  --  Static Timing Analysis (tt_025C_5v00, 100 ns)"
puts "=================================================================="
puts "\n---- SETUP (max) worst paths ----"
report_checks -path_delay max -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 3
puts "\n---- HOLD (min) worst paths ----"
report_checks -path_delay min -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 3
puts "\n---- Slack summary ----"
puts "Setup WNS : [expr {[sta::worst_slack -max]}]"
puts "Hold  WNS : [expr {[sta::worst_slack -min]}]"
report_wns
report_tns
report_worst_slack -max
report_worst_slack -min
puts "\n---- Clock skew ----"
report_clock_skew
puts "\n---- Design area ----"
report_design_area
report_check_types -max_slew -max_capacitance -max_fanout -violators
