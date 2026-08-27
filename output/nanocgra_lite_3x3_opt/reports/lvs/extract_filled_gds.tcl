# Magic GDS-based extraction for filled GDS.
# Dummy fill is on dummy-purpose metal layers and should be electrically inert.
gds read ../../gds/nanocgra_lite_3x3_opt_filled.gds
load NanoCGRA_Lite
select top cell
extract no capacitance
extract do local
extract all
ext2spice lvs
ext2spice -o nanocgra_lite_3x3_opt_filled_layout_lvs.spice
puts "MAGIC_FILLED_GDS_EXTRACT_DONE"
quit -noprompt
