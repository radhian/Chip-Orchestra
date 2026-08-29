set setup $env(PDK_ROOT)/gf180mcuD/libs.tech/netgen/gf180mcuD_setup.tcl
set circuit1 [readnet spice nanocgra_lite_3x3_opt_layout_lvs_norm.spice]
set circuit2 [readnet spice nanocgra_lite_3x3_opt_source_lvs.spice]
readnet spice stdcells_from_layout.spice $circuit2
lvs "$circuit1 NanoCGRA_Lite" "$circuit2 NanoCGRA_Lite" $setup comp_final.out
