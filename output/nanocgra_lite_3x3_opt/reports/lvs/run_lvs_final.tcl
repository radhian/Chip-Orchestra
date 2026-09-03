# Netgen LVS: canonical GDS extraction versus populated powered gate netlist.
# No empty normalized stub and no layout-derived source netlist is accepted.
foreach var {UPRJ_ROOT PDK_ROOT} {
    if {![info exists env($var)] || $env($var) eq ""} {
        error "$var must be set"
    }
}
set pkg [file join $env(UPRJ_ROOT) output nanocgra_lite_3x3_opt]
set lvs_dir [file join $pkg reports lvs]
set layout [file join $lvs_dir nanocgra_lite_3x3_opt_layout_lvs.spice]
set powered_verilog [file join $pkg pnr nanocgra_lite_3x3_opt.pnr.pwr.v]
set source [file join $lvs_dir nanocgra_lite_3x3_opt_source_lvs.spice]
set converter [file join $lvs_dir verilog_to_lvs_spice.py]
set cells [file join $env(PDK_ROOT) gf180mcuD libs.ref gf180mcu_fd_sc_mcu7t5v0 cdl gf180mcu_fd_sc_mcu7t5v0.cdl]
set cells_source [file join $lvs_dir gf180mcu_fd_sc_mcu7t5v0.source.cdl]
file copy -force $cells $cells_source
set setup [file join $env(PDK_ROOT) gf180mcuD libs.tech netgen gf180mcuD_setup.tcl]
set output [file join $lvs_dir comp_final.out]
set marker [file join $lvs_dir netgen.complete]
file delete -force $marker
foreach path [list $layout $powered_verilog $converter $cells $setup] {
    if {![file exists $path] || [file size $path] == 0} { error "missing or empty LVS input: $path" }
}
exec python3 $converter --verilog $powered_verilog --cdl $cells --output $source
if {![file exists $source] || [file size $source] == 0} { error "powered-Verilog conversion produced no source SPICE" }
set circuit1 [readnet spice $layout]
# The source hierarchy is deterministically generated from the powered gate-level
# Verilog; official PDK CDL supplies standard-cell transistor definitions.
set circuit2 [readnet spice $source]
readnet spice $cells_source $circuit2
lvs "$circuit1 NanoCGRA_Lite" "$circuit2 NanoCGRA_Lite" $setup $output
file delete -force $cells_source
set fh [open $output r]
set comparison [read $fh]
close $fh
if {![regexp {Netlists match uniquely|Circuits match uniquely} $comparison]} {
    error "LVS comparison failed; inspect $output"
}
set fh [open $marker w]
puts $fh "NETGEN_LVS_PASSED"
close $fh
puts "NETGEN_LVS_PASSED"
