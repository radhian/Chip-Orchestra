# Post-route PDNSim run. Completion markers mean the command ran, not that IR passed.
foreach var {UPRJ_ROOT PDK_ROOT} {
    if {![info exists ::env($var)] || $::env($var) eq ""} { error "$var must be set" }
}
set OUT [file join $::env(UPRJ_ROOT) output nanocgra_lite_3x3_opt]
set RPT [file join $OUT reports]
set ODB [file join $OUT pnr nanocgra_lite_3x3_opt.odb]
set LIB [file join $::env(PDK_ROOT) gf180mcuD libs.ref gf180mcu_fd_sc_mcu7t5v0 lib gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib]
file mkdir $RPT
file delete -force [file join $RPT pdnsim.complete] [file join $RPT pdnsim.unavailable]
if {![file exists $ODB]} { error "PDNSim requires the post-route ODB: $ODB" }
read_liberty $LIB
read_db $ODB
if {![llength [info commands analyze_power_grid]]} {
    set fh [open [file join $RPT pdnsim.unavailable] w]
    puts $fh "analyze_power_grid is unavailable in this OpenROAD build"
    close $fh
    error "PDNSim unavailable"
}
set_pdnsim_net_voltage -net vdd -voltage 5.0
set_pdnsim_net_voltage -net vss -voltage 0.0
analyze_power_grid -net vdd -outfile [file join $RPT pdnsim_vdd.rpt]
analyze_power_grid -net vss -outfile [file join $RPT pdnsim_vss.rpt]
set fh [open [file join $RPT pdnsim.complete] w]
puts $fh "PDNSIM_COMPLETED; inspect reports and error files"
close $fh
puts "PDNSIM_COMPLETED"
