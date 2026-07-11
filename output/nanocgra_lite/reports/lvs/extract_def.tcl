# Magic DEF-based extraction -> SPICE for LVS (preserves VDD/VSS net names)
# Full-transistor cell views are auto-loaded from the mag search path (MAGTYPE=mag)
set PDKPATH $env(PDK_ROOT)/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
lef read $PDKPATH/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
def read ../../pnr/nanocgra_lite.def
load NanoCGRA_Lite
select top cell
extract no capacitance
extract do local
extract all
ext2spice lvs
ext2spice -o nanocgra_lite_layout_def.spice
puts "MAGIC_DEF_EXTRACT_DONE"
quit -noprompt
