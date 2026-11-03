set SCDIR /workspace/iris_c3a247b9-0025-43e1-bae8-42a940fa0b63/.pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
set OUT /workspace/iris_c3a247b9-0025-43e1-bae8-42a940fa0b63/Chip-Orchestra/output/nanocgra_lite_3x3_opt
set CORNER_LIB $SCDIR/lib/gf180mcu_fd_sc_mcu7t5v0__ff_n40C_5v50.lib
set CORNER_NAME ff_n40C_5v50
read_liberty $CORNER_LIB
read_lef $SCDIR/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
read_lef $SCDIR/lef/gf180mcu_fd_sc_mcu7t5v0.lef
read_def $OUT/pnr/nanocgra_lite_3x3_opt.def
create_clock -name clk -period 100.0 [get_ports clk]
set_input_delay  20.0 -clock clk [get_ports {rst_n uart_rx}]
set_output_delay 20.0 -clock clk [all_outputs]
set_propagated_clock [all_clocks]
set_wire_rc -signal -layer Metal3
set_wire_rc -clock -layer Metal4
estimate_parasitics -placement
puts "NanoCGRA_Lite OPT STA $CORNER_NAME"
report_checks -path_delay max -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 5
report_checks -path_delay min -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 5
puts "Setup WNS : [sta::worst_slack -max]"
puts "Hold  WNS : [sta::worst_slack -min]"
report_wns
report_tns
report_worst_slack -max
report_worst_slack -min
report_check_types -max_slew -max_capacitance -max_fanout -violators
exit
