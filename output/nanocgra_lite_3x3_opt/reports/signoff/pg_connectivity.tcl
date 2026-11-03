foreach var {UPRJ_ROOT PDK_ROOT} {
    if {![info exists ::env($var)] || $::env($var) eq ""} { error "$var must be set" }
}
set OUT [file join $::env(UPRJ_ROOT) output nanocgra_lite_3x3_opt]
set LIB [file join $::env(PDK_ROOT) gf180mcuD libs.ref gf180mcu_fd_sc_mcu7t5v0 lib gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib]
read_liberty $LIB
read_db [file join $OUT pnr nanocgra_lite_3x3_opt.odb]
set_pdnsim_net_voltage -net vdd -voltage 5.0
set_pdnsim_net_voltage -net vss -voltage 0.0
puts "NanoCGRA_Lite internal PDN connectivity"
check_power_grid -net vdd
check_power_grid -net vss
puts "PG_CONNECTIVITY_CHECK_COMPLETED"
