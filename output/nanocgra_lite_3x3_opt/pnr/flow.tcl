# OpenROAD P&R flow for NanoCGRA_Lite 3x3+32B aligned to the D04 template.
set PDK   $::env(PDK_ROOT)/gf180mcuD
set SCDIR $PDK/libs.ref/gf180mcu_fd_sc_mcu7t5v0
set LIB   $SCDIR/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib
set TLEF  $SCDIR/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
set CLEF  $SCDIR/lef/gf180mcu_fd_sc_mcu7t5v0.lef
set NETL  output/nanocgra_lite_3x3_opt/synth/nanocgra_lite_3x3_opt.synth.v
set OUT   output/nanocgra_lite_3x3_opt
set TOP   NanoCGRA_Lite

read_liberty $LIB
read_lef $TLEF
read_lef $CLEF
read_verilog $NETL
link_design $TOP

create_clock -name clk -period 100.0 [get_ports clk]
set clk_period 100.0
set_input_delay  [expr 0.20*$clk_period] -clock clk [get_ports {rst_n uart_rx uart_tx_IN}]
set_output_delay [expr 0.20*$clk_period] -clock clk [all_outputs]
set_driving_cell -lib_cell gf180mcu_fd_sc_mcu7t5v0__inv_1 -pin ZN [get_ports {rst_n uart_rx uart_tx_IN}]
set_load 0.05 [all_outputs]
set_wire_rc -signal -layer Metal3
set_wire_rc -clock  -layer Metal4

initialize_floorplan -die_area {0 0 550 550} -core_area {10 10 540 540} \
    -site GF018hv5v_mcu_sc7
make_tracks

puts "=== DIE/CORE AREA AFTER FLOORPLAN ==="
set die  [ord::get_die_area]
set core [ord::get_core_area]
puts "DIE  = $die"
puts "CORE = $core"

place_pin -pin_name vss           -layer Metal2 -location {0.5 82.5}   -pin_size {1.0 72.28}
place_pin -pin_name clk_PU        -layer Metal2 -location {0.5 213.845} -pin_size {1.0 1.04}
place_pin -pin_name clk_PD        -layer Metal2 -location {0.5 209.48}  -pin_size {1.0 1.04}
place_pin -pin_name clk           -layer Metal2 -location {0.5 148.95}  -pin_size {1.0 1.04}
place_pin -pin_name rst_n_PU      -layer Metal2 -location {0.5 313.845} -pin_size {1.0 1.04}
place_pin -pin_name rst_n_PD      -layer Metal2 -location {0.5 309.48}  -pin_size {1.0 1.04}
place_pin -pin_name rst_n         -layer Metal2 -location {0.5 248.95}  -pin_size {1.0 1.04}
place_pin -pin_name uart_rx_PU    -layer Metal2 -location {0.5 413.845} -pin_size {1.0 1.04}
place_pin -pin_name uart_rx_PD    -layer Metal2 -location {0.5 409.48}  -pin_size {1.0 1.04}
place_pin -pin_name uart_rx       -layer Metal2 -location {0.5 348.95}  -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_SL    -layer Metal2 -location {0.5 440.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_OE    -layer Metal2 -location {0.5 446.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_IN    -layer Metal2 -location {0.5 452.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_OUT   -layer Metal2 -location {0.5 458.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_IE    -layer Metal2 -location {0.5 494.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_PD    -layer Metal2 -location {0.5 500.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_PDRV1 -layer Metal2 -location {0.5 506.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_PDRV0 -layer Metal2 -location {0.5 512.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_PU    -layer Metal2 -location {0.5 518.0}   -pin_size {1.0 1.04}
place_pin -pin_name uart_tx_CS    -layer Metal2 -location {0.5 524.0}   -pin_size {1.0 1.04}
place_pin -pin_name vdd           -layer Metal2 -location {67.5 549.5}  -pin_size {72.28 1.0}

tapcell -distance 20 \
    -tapcell_master gf180mcu_fd_sc_mcu7t5v0__filltie \
    -endcap_master  gf180mcu_fd_sc_mcu7t5v0__endcap

add_global_connection -net vdd -pin_pattern {^VDD$}  -power
add_global_connection -net vdd -pin_pattern {^VNW$}  -power
add_global_connection -net vss -pin_pattern {^VSS$}  -ground
add_global_connection -net vss -pin_pattern {^VPW$}  -ground
set_voltage_domain -name CORE -power vdd -ground vss
define_pdn_grid -name stdcell_grid -voltage_domains CORE
add_pdn_stripe -grid stdcell_grid -layer Metal1 -width 0.6 -followpins
add_pdn_stripe -grid stdcell_grid -layer Metal4 -width 1.6 -pitch 40 -offset 10
add_pdn_stripe -grid stdcell_grid -layer Metal5 -width 1.6 -pitch 40 -offset 10
add_pdn_connect -grid stdcell_grid -layers {Metal1 Metal4}
add_pdn_connect -grid stdcell_grid -layers {Metal4 Metal5}
pdngen

global_placement -density 0.70
estimate_parasitics -placement
repair_design
detailed_placement
optimize_mirroring
check_placement -verbose

estimate_parasitics -placement
repair_timing -setup -hold

set_routing_layers -signal Metal1-Metal5 -clock Metal1-Metal5
global_route
detailed_route

check_antennas -report_file $OUT/reports/check_antennas.rpt
check_power_grid -net vdd
check_power_grid -net vss

report_tns
report_wns
report_checks -path_delay max -format full_clock_expanded -fields {slew cap input nets fanout} \
    > $OUT/reports/sta.txt
write_verilog $OUT/pnr/nanocgra_lite_3x3_opt.pnr.v
write_verilog -include_pwr_gnd $OUT/pnr/nanocgra_lite_3x3_opt.pnr.pwr.v
write_def $OUT/pnr/nanocgra_lite_3x3_opt.def
