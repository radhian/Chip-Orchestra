set ::env(STEP_ID) OpenROAD.STAPrePNR
set ::env(TECH_LEF) /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
set ::env(MACRO_LEFS) ""
set ::env(STD_CELL_LIBRARY) gf180mcu_fd_sc_mcu7t5v0
set ::env(VDD_PIN) VDD
set ::env(GND_PIN) VSS
set ::env(TECH_LEFS) "\"nom_*\" /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef \"min_*\" /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__min.tlef \"max_*\" /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__max.tlef"
set ::env(PRIMARY_GDSII_STREAMOUT_TOOL) klayout
set ::env(DEFAULT_CORNER) nom_tt_025C_5v00
set ::env(STA_CORNERS) "nom_tt_025C_5v00 nom_ss_125C_4v50 nom_ff_n40C_5v50"
set ::env(RT_MIN_LAYER) Metal2
set ::env(RT_MAX_LAYER) Metal5
set ::env(SCL_GROUND_PINS) "VSS VPW"
set ::env(SCL_POWER_PINS) "VDD VNW"
set ::env(TRISTATE_CELLS) "\"gf180mcu_fd_sc_mcu7t5v0__bufz*\""
set ::env(FILL_CELLS) "\"gf180mcu_fd_sc_mcu7t5v0__fill_*\""
set ::env(DECAP_CELLS) "\"gf180mcu_fd_sc_mcu7t5v0__fillcap_*\""
set ::env(LIB) "\"*_tt_025C_5v00\" /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib \"*_ss_125C_4v50\" /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__ss_125C_4v50.lib \"*_ff_n40C_5v50\" /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__ff_n40C_5v50.lib"
set ::env(CELL_LEFS) /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef
set ::env(CELL_GDS) /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/gds/gf180mcu_fd_sc_mcu7t5v0.gds
set ::env(CELL_VERILOG_MODELS) "/home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/gf180mcu_fd_sc_mcu7t5v0.v /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/primitives.v"
set ::env(CELL_SPICE_MODELS) /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice
set ::env(CELL_CDLS) /home/wlmoi/.volare/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/cdl/gf180mcu_fd_sc_mcu7t5v0.cdl
set ::env(SYNTH_EXCLUDED_CELL_FILE) /home/wlmoi/.volare/gf180mcuD/libs.tech/openlane/gf180mcu_fd_sc_mcu7t5v0/no_synth.cells
set ::env(PNR_EXCLUDED_CELL_FILE) /home/wlmoi/.volare/gf180mcuD/libs.tech/openlane/gf180mcu_fd_sc_mcu7t5v0/drc_exclude.cells
set ::env(OUTPUT_CAP_LOAD) 72.91
set ::env(MAX_FANOUT_CONSTRAINT) 10
set ::env(MAX_TRANSITION_CONSTRAINT) 3.0
set ::env(MAX_CAPACITANCE_CONSTRAINT) 0.2
set ::env(CLOCK_UNCERTAINTY_CONSTRAINT) 0.25
set ::env(CLOCK_TRANSITION_CONSTRAINT) 0.1499999999999999944488848768742172978818416595458984375
set ::env(TIME_DERATING_CONSTRAINT) 5.0
set ::env(IO_DELAY_CONSTRAINT) 20.0
set ::env(SYNTH_DRIVING_CELL) gf180mcu_fd_sc_mcu7t5v0__inv_1/ZN
set ::env(SYNTH_CLK_DRIVING_CELL) gf180mcu_fd_sc_mcu7t5v0__inv_4/ZN
set ::env(SYNTH_TIEHI_CELL) gf180mcu_fd_sc_mcu7t5v0__tieh/Z
set ::env(SYNTH_TIELO_CELL) gf180mcu_fd_sc_mcu7t5v0__tiel/ZN
set ::env(SYNTH_BUFFER_CELL) gf180mcu_fd_sc_mcu7t5v0__buf_1/I/Z
set ::env(PLACE_SITE) GF018hv5v_mcu_sc7
set ::env(CELL_PAD_EXCLUDE) "gf180mcu_fd_sc_mcu7t5v0__filltie \"gf180mcu_fd_sc_mcu7t5v0__fill_*\" gf180mcu_fd_sc_mcu7t5v0__endcap"
set ::env(DIODE_CELL) gf180mcu_fd_sc_mcu7t5v0__antenna/I
set ::env(WELLTAP_CELL) gf180mcu_fd_sc_mcu7t5v0__filltie
set ::env(ENDCAP_CELL) gf180mcu_fd_sc_mcu7t5v0__endcap
set ::env(DESIGN_NAME) NanoCGRA_Lite
set ::env(CLOCK_PERIOD) 100.0
set ::env(CLOCK_PORT) clk
set ::env(FALLBACK_SDC) /mnt/d/LinkedinProjects/Chip-Orchestra/paper/eda_runtime/librelane/scripts/base.sdc
set ::env(PAD_EDGE_SPACING) 0.0
set ::env(SET_RC_VERBOSE) 0
set ::env(PDN_CONNECT_MACROS_TO_GRID) 1
set ::env(PDN_ENABLE_GLOBAL_CONNECTIONS) 1
set ::env(DEDUPLICATE_CORNERS) 0
set ::env(STA_MACRO_PRIORITIZE_NL) 1
set ::env(CURRENT_NL) /mnt/d/LinkedinProjects/Chip-Orchestra/paper/nanocgra_e2e_20261011/exports/harden/chip/runs/RUN_2026-10-11_14-45-43/06-yosys-synthesis/NanoCGRA_Lite.nl.v
set ::env(SAVE_SDC) /mnt/d/LinkedinProjects/Chip-Orchestra/paper/nanocgra_e2e_20261011/exports/harden/chip/runs/RUN_2026-10-11_14-45-43/12-openroad-staprepnr/NanoCGRA_Lite.sdc
set ::env(OPENLANE_SDC_IDEAL_CLOCKS) 1
