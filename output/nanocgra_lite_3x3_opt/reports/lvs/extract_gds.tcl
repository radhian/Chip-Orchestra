# Magic extraction of the canonical, unfilled GDS.
# Invoke with UPRJ_ROOT and PDK_ROOT set; cwd is intentionally irrelevant.
foreach var {UPRJ_ROOT PDK_ROOT} {
    if {![info exists ::env($var)] || $::env($var) eq ""} {
        error "$var must be set"
    }
}
set pkg [file join $::env(UPRJ_ROOT) output nanocgra_lite_3x3_opt]
set lvs_dir [file join $pkg reports lvs]
set gds_file [file join $pkg gds nanocgra_lite_3x3_opt.gds]
set spice_file [file join $lvs_dir nanocgra_lite_3x3_opt_layout_lvs.spice]
set marker [file join $lvs_dir extraction.complete]
file delete -force $marker
if {![file exists $gds_file] || [file size $gds_file] == 0} {
    error "canonical GDS is missing or empty: $gds_file"
}
file mkdir $lvs_dir
cd $lvs_dir
gds read $gds_file
load NanoCGRA_Lite
select top cell
extract no capacitance
extract do local
extract all
ext2spice lvs
ext2spice -o $spice_file
if {![file exists $spice_file] || [file size $spice_file] == 0} {
    error "Magic did not produce non-empty layout SPICE"
}
exec python3 [file join $lvs_dir normalize_magic_devices.py] $spice_file
foreach scratch [glob -nocomplain [file join $lvs_dir *.ext]] {
    file delete -force $scratch
}
set fh [open $marker w]
puts $fh "MAGIC_GDS_EXTRACTION_COMPLETED"
close $fh
puts "MAGIC_GDS_EXTRACTION_COMPLETED"
quit -noprompt
