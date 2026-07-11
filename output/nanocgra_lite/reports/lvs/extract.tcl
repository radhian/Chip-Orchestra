# Magic GDS extraction -> SPICE for LVS
gds read ../../gds/nanocgra_lite.gds
load NanoCGRA_Lite
select top cell
extract no all
extract do local
extract all
ext2spice lvs
ext2spice -o nanocgra_lite.ext.spice
puts "MAGIC_EXTRACT_DONE"
quit -noprompt
