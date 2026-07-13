source $::env(PDK_ROOT)/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl
# Ignore physical-only fill / tap / endcap cells (present in the source
# physical netlist, absent from the magic device-level extraction) so the
# power-rail fanout matches between the two views.
foreach fc {endcap filltie fill_1 fill_2 fill_4 fill_8 fill_16 fill_32 fill_64} {
    catch {ignore class "-circuit1 gf180mcu_fd_sc_mcu7t5v0__$fc"}
    catch {ignore class "-circuit2 gf180mcu_fd_sc_mcu7t5v0__$fc"}
}
# Seed the partition: extracted-layout rails == source logical rails.
equate nodes "-circuit1 NanoCGRA_Lite" "PHY_9/VDD" "-circuit2 NanoCGRA_Lite" VDD
equate nodes "-circuit1 NanoCGRA_Lite" VSUBS "-circuit2 NanoCGRA_Lite" VSS
