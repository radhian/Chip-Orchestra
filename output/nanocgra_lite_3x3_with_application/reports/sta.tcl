read_liberty /opt/pdk/ciel/gf180mcu/versions/54435919abffb937387ec956209f9cf5fd2dfbee/gf180mcuA/libs.ref/gf180mcu_fd_io/lib/gf180mcu_fd_io__ff_125C_2v75.lib
read_verilog /tmp/chip-orchestra/workspaces/dbe7af46-366c-421b-8cf3-daafc5a7ae6a/exports/harden/chip/runs/RUN_2026-08-16_06-21-45/final/nl/nano_cgra_3x3_sobel_accelerator_v4.nl.v
link_design nano_cgra_3x3_sobel_accelerator_v4
read_sdc /tmp/chip-orchestra/workspaces/dbe7af46-366c-421b-8cf3-daafc5a7ae6a/exports/harden/chip/runs/RUN_2026-08-16_06-21-45/final/sdc/nano_cgra_3x3_sobel_accelerator_v4.sdc
report_checks -path_delay min_max > /dev/stdout
report_wns
report_tns
set_power_activity -input -activity 0.1
report_power
exit
