foreach var {UPRJ_ROOT PDK_ROOT} {
    if {![info exists ::env($var)] || $::env($var) eq ""} { error "$var must be set" }
}
set OUT [file join $::env(UPRJ_ROOT) output nanocgra_lite_3x3_opt]
set SCDIR [file join $::env(PDK_ROOT) gf180mcuD libs.ref gf180mcu_fd_sc_mcu7t5v0]
read_lef [file join $OUT pnr gf180mcu_fd_sc_mcu7t5v0__drc_clean.tlef]
read_lef [file join $SCDIR lef gf180mcu_fd_sc_mcu7t5v0.lef]
read_def [file join $OUT pnr nanocgra_lite_3x3_opt.def]
set parsed_odb [file join $OUT pnr nanocgra_lite_3x3_opt.final_def.odb]
write_db $parsed_odb
file delete -force $parsed_odb
puts "FINAL_DELIVERABLE_DEF_PARSED"
