# Magic DEF-based extraction -> SPICE for LVS (opt variant).
# Relies on the PDK .magicrc (copied into this dir) being auto-sourced by
# magic, which loads the gf180mcuD tech + addpaths to the .mag cell views.
# This mirrors the working sister-variant (nanocgra_lite_3x3_32b) flow.
set PDKPATH $env(PDK_ROOT)/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
lef read $PDKPATH/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
def read ../../pnr/nanocgra_lite_3x3_opt.def
load NanoCGRA_Lite
select top cell
extract no capacitance
extract do local
extract all
ext2spice lvs
ext2spice -o nanocgra_lite_3x3_opt_layout_def.spice
puts "MAGIC_DEF_EXTRACT_DONE"
quit -noprompt
