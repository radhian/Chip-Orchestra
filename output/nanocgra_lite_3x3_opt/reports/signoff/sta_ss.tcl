foreach var {UPRJ_ROOT PDK_ROOT} {
    if {![info exists ::env($var)] || $::env($var) eq ""} { error "$var must be set" }
}
set OUT [file join $::env(UPRJ_ROOT) output nanocgra_lite_3x3_opt]
set SCDIR [file join $::env(PDK_ROOT) gf180mcuD libs.ref gf180mcu_fd_sc_mcu7t5v0]
set CORNER_LIB [file join $SCDIR lib gf180mcu_fd_sc_mcu7t5v0__ss_125C_4v50.lib]
read_liberty $CORNER_LIB
read_db [file join $OUT pnr nanocgra_lite_3x3_opt.odb]
create_clock -name clk -period 100.0 [get_ports clk]
set_input_delay 20.0 -clock clk [get_ports {rst_n uart_rx uart_tx_IN}]
set_output_delay 20.0 -clock clk [all_outputs]
set_propagated_clock [all_clocks]
puts "NanoCGRA_Lite post-route STA: ss_125C_4v50"
report_checks -path_delay max -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 20
report_checks -path_delay min -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 20
report_wns
report_tns
report_worst_slack -max
report_worst_slack -min
report_clock_skew
report_design_area
report_check_types -max_slew -max_capacitance -max_fanout -violators
