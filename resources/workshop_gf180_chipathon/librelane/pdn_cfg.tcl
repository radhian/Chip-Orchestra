# GF180 Chipathon Workshop — power delivery network configuration
# PDN for the chip core area within the pad ring.

set ::env(FP_PDN_ENABLE_RAILS) 1
set ::env(FP_PDN_CORE_RING) 1
set ::env(FP_PDN_RAIL_WIDTH) 0.48

# Vertical straps (DVDD/DVSS)
set ::env(FP_PDN_VWIDTH) 1.6
set ::env(FP_PDN_VPITCH) 50
set ::env(FP_PDN_VOFFSET) 5

# Horizontal straps
set ::env(FP_PDN_HWIDTH) 1.6
set ::env(FP_PDN_HPITCH) 50
set ::env(FP_PDN_HOFFSET) 5
