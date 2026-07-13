#==============================================================================
# Frequency sweep (Fmax) for NanoCGRA_Lite OPT 3x3 -- OpenROAD/OpenSTA engine
#   Sweeps clock period: 100,50,20,10,5,2 ns  (10,20,50,100,200,500 MHz)
#   Reports worst setup slack per period; Fmax = last period with slack >= 0.
#==============================================================================
set SCDIR $::env(PDK_ROOT)/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
read_liberty $SCDIR/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib
read_db output/nanocgra_lite_3x3_opt/pnr/nanocgra_lite_3x3_opt.odb

set_wire_rc -signal -layer Metal3
set_wire_rc -clock  -layer Metal4

set periods {100.0 50.0 20.0 10.0 5.0 2.0}

puts "FMAX_SWEEP_BEGIN"
foreach p $periods {
    # rebuild the clock + IO constraints for this period (IO delay = 20% of period)
    create_clock -name clk -period $p [get_ports clk]
    set io [expr {0.20 * $p}]
    set_input_delay  $io -clock clk [all_inputs]
    set_output_delay $io -clock clk [all_outputs]
    set_propagated_clock [all_clocks]
    estimate_parasitics -placement

    set setup_slack [sta::worst_slack -max]
    set hold_slack  [sta::worst_slack -min]
    set freq [expr {1000.0 / $p}]
    puts [format "SWEEP period=%.1fns freq=%.1fMHz setup_slack=%.3fns hold_slack=%.3fns" \
          $p $freq $setup_slack $hold_slack]
}
puts "FMAX_SWEEP_END"
