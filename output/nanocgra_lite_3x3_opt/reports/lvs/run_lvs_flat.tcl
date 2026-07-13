# Flat transistor-level LVS attempt for nanocgra_lite_3x3_opt.
set setup $env(PDK_ROOT)/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl
set circuit1 [readnet spice nanocgra_lite_3x3_opt_layout_lvs.spice]
set circuit2 [readnet verilog nanocgra_lite_3x3_opt.pnr.pwr.lvs.v]
readnet spice stdcells_from_layout.spice $circuit2
flatten class "NanoCGRA_Lite"
lvs "$circuit1 NanoCGRA_Lite" "$circuit2 NanoCGRA_Lite" $setup comp_flat.out
