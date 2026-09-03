# OpenROAD P&R flow for NanoCGRA_Lite 3x3+32B, D04 550 um contract.
# Run from any directory with UPRJ_ROOT=<Chip-Orchestra root> and PDK_ROOT set.
foreach var {UPRJ_ROOT PDK_ROOT} {
    if {![info exists ::env($var)] || $::env($var) eq ""} {
        error "$var must be set"
    }
}
set PDK   [file join $::env(PDK_ROOT) gf180mcuD]
set SCDIR [file join $PDK libs.ref gf180mcu_fd_sc_mcu7t5v0]
set LIB   [file join $SCDIR lib gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib]
set TLEF  [file join $SCDIR techlef gf180mcu_fd_sc_mcu7t5v0__nom.tlef]
set CLEF  [file join $SCDIR lef gf180mcu_fd_sc_mcu7t5v0.lef]
set OUT   [file join $::env(UPRJ_ROOT) output nanocgra_lite_3x3_opt]
set NETL  [file join $OUT synth nanocgra_lite_3x3_opt.synth.v]
set RPT   [file join $OUT reports]
set TOP   NanoCGRA_Lite
file mkdir $RPT [file join $RPT signoff] [file join $OUT pnr]

proc write_marker {path text} {
    set fh [open $path w]
    puts $fh $text
    close $fh
}

proc run_global_connect {} {
    if {[llength [info commands global_connect]]} {
        global_connect
    } else {
        puts "WARN: this OpenROAD build applies add_global_connection immediately and has no global_connect command"
    }
}

proc capture_report {path script} {
    sta::redirect_file_begin $path
    set code [catch {uplevel 1 $script} result options]
    sta::redirect_file_end
    if {$code} {
        return -options $options $result
    }
}

read_liberty $LIB
read_lef $TLEF
read_lef $CLEF
read_verilog $NETL
link_design $TOP

create_clock -name clk -period 100.0 [get_ports clk]
set clk_period 100.0
set_input_delay  [expr {0.20*$clk_period}] -clock clk [get_ports {rst_n uart_rx uart_tx_IN}]
set_output_delay [expr {0.20*$clk_period}] -clock clk [all_outputs]
set_driving_cell -lib_cell gf180mcu_fd_sc_mcu7t5v0__inv_1 -pin ZN [get_ports {rst_n uart_rx uart_tx_IN}]
set_load 0.05 [all_outputs]
set_wire_rc -signal -layer Metal3
set_wire_rc -clock  -layer Metal4

# D04 contract: fixed 550 um square and exact boundary pin locations.
initialize_floorplan -die_area {0 0 550 550} -core_area {10 10 540 540} \
    -site GF018hv5v_mcu_sc7
make_tracks
place_pin -pin_name vss           -layer Metal2 -location {0.5 82.5}     -pin_size {1.0 72.28}
place_pin -pin_name clk_PU        -layer Metal2 -location {0.5 213.845}  -pin_size {1.0 0.38}
place_pin -pin_name clk_PD        -layer Metal2 -location {0.5 209.48}   -pin_size {1.0 0.38}
place_pin -pin_name clk           -layer Metal2 -location {0.5 148.95}   -pin_size {1.0 0.38}
place_pin -pin_name rst_n_PU      -layer Metal2 -location {0.5 313.845}  -pin_size {1.0 0.38}
place_pin -pin_name rst_n_PD      -layer Metal2 -location {0.5 309.48}   -pin_size {1.0 0.38}
place_pin -pin_name rst_n         -layer Metal2 -location {0.5 248.95}   -pin_size {1.0 0.38}
place_pin -pin_name uart_rx_PU    -layer Metal2 -location {0.5 413.845}  -pin_size {1.0 0.38}
place_pin -pin_name uart_rx_PD    -layer Metal2 -location {0.5 409.48}   -pin_size {1.0 0.38}
place_pin -pin_name uart_rx       -layer Metal2 -location {0.5 348.95}   -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_CS    -layer Metal2 -location {0.5 516.45}   -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_SL    -layer Metal2 -location {0.5 451.50}   -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_IE    -layer Metal2 -location {0.5 508.425}  -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_OE    -layer Metal2 -location {0.5 449.20}   -pin_size {1.0 0.28}
place_pin -pin_name uart_tx_PU    -layer Metal2 -location {0.5 513.845}  -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_PD    -layer Metal2 -location {0.5 509.48}   -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_OUT   -layer Metal2 -location {0.5 450.56}   -pin_size {1.0 0.28}
place_pin -pin_name uart_tx_PDRV0 -layer Metal2 -location {0.5 512.7}    -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_PDRV1 -layer Metal2 -location {0.5 511.99}   -pin_size {1.0 0.38}
place_pin -pin_name uart_tx_IN    -layer Metal2 -location {0.5 449.95}   -pin_size {1.0 0.38}
place_pin -pin_name vdd           -layer Metal2 -location {67.5 549.5}   -pin_size {72.28 1.0}

tapcell -distance 20 \
    -tapcell_master gf180mcu_fd_sc_mcu7t5v0__filltie \
    -endcap_master  gf180mcu_fd_sc_mcu7t5v0__endcap

add_global_connection -net vdd -pin_pattern {^VDD$} -power
add_global_connection -net vdd -pin_pattern {^VNW$} -power
add_global_connection -net vss -pin_pattern {^VSS$} -ground
add_global_connection -net vss -pin_pattern {^VPW$} -ground
run_global_connect
set_voltage_domain -name CORE -power vdd -ground vss
define_pdn_grid -name stdcell_grid -voltage_domains CORE
add_pdn_stripe -grid stdcell_grid -layer Metal1 -width 0.6 -followpins
add_pdn_stripe -grid stdcell_grid -layer Metal4 -width 1.6 -pitch 40 -offset 10
add_pdn_stripe -grid stdcell_grid -layer Metal5 -width 1.6 -pitch 40 -offset 10
add_pdn_connect -grid stdcell_grid -layers {Metal1 Metal4}
add_pdn_connect -grid stdcell_grid -layers {Metal4 Metal5}
pdngen

# The D04 Metal2 boundary PG pins are connected to the generated Metal4 grid
# after DEF export, once exact reference pin geometry has been applied.

global_placement -density 0.70
estimate_parasitics -placement
repair_design
detailed_placement
optimize_mirroring
check_placement -verbose

clock_tree_synthesis \
    -root_buf gf180mcu_fd_sc_mcu7t5v0__clkbuf_16 \
    -buf_list {gf180mcu_fd_sc_mcu7t5v0__clkbuf_2 gf180mcu_fd_sc_mcu7t5v0__clkbuf_4 gf180mcu_fd_sc_mcu7t5v0__clkbuf_8 gf180mcu_fd_sc_mcu7t5v0__clkbuf_16} \
    -sink_clustering_enable
set_propagated_clock [all_clocks]
estimate_parasitics -placement
repair_clock_nets
run_global_connect
detailed_placement
repair_timing -setup -hold
detailed_placement

set_routing_layers -signal Metal2-Metal5 -clock Metal2-Metal5
global_route -guide_file [file join $OUT pnr route.guide]
estimate_parasitics -global_routing
detailed_route -output_drc [file join $RPT route_drc.rpt] -verbose 1

# Exact available GF180 fill family, largest first; no project-generated dummy fill.
set FILLERS {gf180mcu_fd_sc_mcu7t5v0__fill_16 gf180mcu_fd_sc_mcu7t5v0__fill_8 gf180mcu_fd_sc_mcu7t5v0__fill_4 gf180mcu_fd_sc_mcu7t5v0__fill_2 gf180mcu_fd_sc_mcu7t5v0__fill_1}
filler_placement $FILLERS
check_placement -verbose
run_global_connect

estimate_parasitics -global_routing
set_propagated_clock [all_clocks]
capture_report [file join $RPT sta_max.rpt] {
    report_checks -path_delay max -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 20
    report_wns
    report_tns
    report_worst_slack -max
}
capture_report [file join $RPT sta_min.rpt] {
    report_checks -path_delay min -format full_clock_expanded -fields {slew cap input net fanout} -digits 3 -group_count 20
    report_worst_slack -min
    report_clock_skew
}
capture_report [file join $RPT electrical_limits.rpt] {
    report_check_types -max_slew -max_capacitance -max_fanout -violators
}
capture_report [file join $RPT design_area.rpt] { report_design_area }
capture_report [file join $RPT power.rpt] { report_power }
check_antennas -report_file [file join $RPT check_antennas.rpt]
capture_report [file join $RPT pg_vdd.rpt] { check_power_grid -net vdd }
capture_report [file join $RPT pg_vss.rpt] { check_power_grid -net vss }
write_marker [file join $RPT pg_checks.complete] "PG_CHECKS_COMPLETED"

write_verilog [file join $OUT pnr nanocgra_lite_3x3_opt.pnr.v]
write_verilog -include_pwr_gnd [file join $OUT pnr nanocgra_lite_3x3_opt.pnr.pwr.v]
write_def [file join $OUT pnr nanocgra_lite_3x3_opt.def]
if {[llength [info commands write_db]]} {
    write_db [file join $OUT pnr nanocgra_lite_3x3_opt.odb]
    write_marker [file join $RPT odb_write.complete] "ODB_WRITE_COMPLETED"
} else {
    write_marker [file join $RPT odb_write.unavailable] "write_db is unavailable in this OpenROAD build"
}
# OpenROAD place_pin cannot express D04's disjoint PG rectangles. Apply the
# tracked reference geometry to the deliverable DEF, preserving routed net names.
exec python3 [file join $OUT pnr apply_d04_pin_contract.py] \
    [file join $OUT pnr D04.def] \
    [file join $OUT pnr nanocgra_lite_3x3_opt.def]
# Add deterministic M2-M3-M4 special routes from the D04 vdd/vss pins to
# existing PDN stripe intersections, then require an independent connectivity check.
exec python3 [file join $OUT pnr connect_d04_pg.py] \
    [file join $OUT pnr nanocgra_lite_3x3_opt.def]
exec python3 [file join $OUT pnr check_d04_pg.py] \
    [file join $OUT pnr nanocgra_lite_3x3_opt.def]
write_marker [file join $RPT flow.complete] "OPENROAD_FLOW_COMPLETED"
puts "FLOW_DONE"
