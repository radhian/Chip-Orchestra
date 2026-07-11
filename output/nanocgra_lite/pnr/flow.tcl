#==============================================================================
# OpenROAD P&R flow for NanoCGRA_Lite  (GF180MCU, gf180mcu_fd_sc_mcu7t5v0)
#==============================================================================
set PDK   $::env(PDK_ROOT)/gf180mcuD
set SCDIR $PDK/libs.ref/gf180mcu_fd_sc_mcu7t5v0
set LIB   $SCDIR/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib
set TLEF  $SCDIR/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
set CLEF  $SCDIR/lef/gf180mcu_fd_sc_mcu7t5v0.lef
set NETL  output/nanocgra_lite/synth/nanocgra_lite.synth.v
set OUT   output/nanocgra_lite
set TOP   NanoCGRA_Lite

# ---- Read inputs ----
read_liberty $LIB
read_lef $TLEF
read_lef $CLEF
read_verilog $NETL
link_design $TOP

# ---- Constraints ----
create_clock -name clk -period 100.0 [get_ports clk]
set clk_period 100.0
set_input_delay  [expr 0.20*$clk_period] -clock clk [all_inputs]
set_output_delay [expr 0.20*$clk_period] -clock clk [all_outputs]
set_driving_cell -lib_cell gf180mcu_fd_sc_mcu7t5v0__inv_1 -pin ZN [all_inputs]
set_load 0.05 [all_outputs]
set_wire_rc -signal -layer Metal3
set_wire_rc -clock  -layer Metal4

# ---- Floorplan: ~62% utilization, square, 10um core margin ----
initialize_floorplan -utilization 62 -aspect_ratio 1.0 -core_space 10.0 \
    -site GF018hv5v_mcu_sc7
make_tracks

puts "=== DIE/CORE AREA AFTER FLOORPLAN ==="
set die  [ord::get_die_area]
set core [ord::get_core_area]
puts "DIE  = $die"
puts "CORE = $core"

# ---- IO pin placement ----
place_pins -hor_layers Metal3 -ver_layers Metal2

# ---- Tap/endcap ----
tapcell -distance 20 \
    -tapcell_master gf180mcu_fd_sc_mcu7t5v0__filltie \
    -endcap_master  gf180mcu_fd_sc_mcu7t5v0__endcap

# ---- Power grid ----
add_global_connection -net VDD -pin_pattern {^VDD$}  -power
add_global_connection -net VDD -pin_pattern {^VNW$}  -power
add_global_connection -net VSS -pin_pattern {^VSS$}  -ground
add_global_connection -net VSS -pin_pattern {^VPW$}  -ground
set_voltage_domain -name CORE -power VDD -ground VSS
define_pdn_grid -name stdcell_grid -voltage_domains CORE
add_pdn_stripe -grid stdcell_grid -layer Metal1 -width 0.6 -followpins
add_pdn_stripe -grid stdcell_grid -layer Metal4 -width 1.6 -pitch 40 -offset 10
add_pdn_stripe -grid stdcell_grid -layer Metal5 -width 1.6 -pitch 40 -offset 10
add_pdn_connect -grid stdcell_grid -layers {Metal1 Metal4}
add_pdn_connect -grid stdcell_grid -layers {Metal4 Metal5}
pdngen

# ---- Global placement ----
global_placement -density 0.70
estimate_parasitics -placement
repair_design
detailed_placement
optimize_mirroring
check_placement -verbose

# ---- Clock tree synthesis ----
clock_tree_synthesis \
    -root_buf gf180mcu_fd_sc_mcu7t5v0__clkbuf_16 \
    -buf_list {gf180mcu_fd_sc_mcu7t5v0__clkbuf_2 gf180mcu_fd_sc_mcu7t5v0__clkbuf_4 gf180mcu_fd_sc_mcu7t5v0__clkbuf_8 gf180mcu_fd_sc_mcu7t5v0__clkbuf_16} \
    -sink_clustering_enable
set_propagated_clock [all_clocks]
estimate_parasitics -placement
repair_clock_nets
detailed_placement

# ---- Routing ----
set_routing_layers -signal Metal2-Metal5 -clock Metal2-Metal5
global_route -guide_file $OUT/pnr/route.guide
estimate_parasitics -global_routing
detailed_route -output_drc $OUT/reports/route_drc.rpt -verbose 1

# ---- Fillers ----
filler_placement gf180mcu_fd_sc_mcu7t5v0__fill_*
check_placement

# ---- Final parasitics + STA ----
estimate_parasitics -global_routing
set_propagated_clock [all_clocks]

puts "=================== STA REPORT ==================="
report_checks -path_delay max -fields {slew cap input net fanout} -digits 3
report_checks -path_delay min -fields {slew cap input net fanout} -digits 3
report_wns
report_tns
report_worst_slack -max
report_worst_slack -min
report_clock_skew
report_design_area

# ---- Write outputs ----
write_def $OUT/pnr/nanocgra_lite.def
write_verilog $OUT/pnr/nanocgra_lite.pnr.v
write_db $OUT/pnr/nanocgra_lite.odb

puts "FLOW_DONE"
