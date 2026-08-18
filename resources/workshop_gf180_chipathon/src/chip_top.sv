// GF180 Chipathon Workshop — Chip-level top with pad instances
// Golden test fixture pad population:
//   60 analog (gf180mcu_fd_io__asig_5p0)
//   20 bidirectional (gf180mcu_fd_io__bi_24t)
//    4 DVDD (gf180mcu_fd_io__dvdd)
//    4 DVSS (gf180mcu_fd_io__dvss)
//    2 dedicated input (gf180mcu_fd_io__in_s)
//    4 corner (gf180mcu_fd_io__cor)
//
// This is the WORKSHOP-SPECIFIC RTL. Generic Chip Orchestra designs
// will have different pad populations.

`include "slot_defines.svh"

module chip_top (
    inout wire clk,
    inout wire rst_n
);

    // Core instance
    chip_core u_core (
        .clk(clk),
        .rst_n(rst_n)
    );

    // NOTE: every pad/corner below carries the (* keep *) attribute.  The pads
    // are instantiated without signal connections in this workshop fixture, so
    // Yosys would otherwise optimise them away as dead cells and OpenROAD.PadRing
    // would fail with "No instance ... found".  (* keep *) forces synthesis to
    // preserve the physical instances so the pad ring can place them.

    // ---------------------------------------------------------------
    // Corner pads (4)
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__cor corner_sw ();
    (* keep *) gf180mcu_fd_io__cor corner_se ();
    (* keep *) gf180mcu_fd_io__cor corner_ne ();
    (* keep *) gf180mcu_fd_io__cor corner_nw ();

    // ---------------------------------------------------------------
    // SOUTH — 15 analog + 1 DVSS
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_0  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_1  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_2  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_3  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_4  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_5  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_6  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_7  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_8  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_9  ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_10 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_11 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_12 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_13 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_14 ();
    (* keep *) gf180mcu_fd_io__dvss     pad_s_dvss_0    ();

    // ---------------------------------------------------------------
    // EAST — 10 bidirectional + 1 DVDD + 1 DVSS
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_0  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_1  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_2  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_3  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_4  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_5  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_6  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_7  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_8  ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_9  ();
    (* keep *) gf180mcu_fd_io__dvdd   pad_e_dvdd_0 ();
    (* keep *) gf180mcu_fd_io__dvss   pad_e_dvss_1 ();

    // ---------------------------------------------------------------
    // NORTH — 15 analog + 1 DVDD
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_15 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_16 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_17 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_18 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_19 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_20 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_21 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_22 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_23 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_24 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_25 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_26 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_27 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_28 ();
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_29 ();
    (* keep *) gf180mcu_fd_io__dvdd     pad_n_dvdd_1    ();

    // ---------------------------------------------------------------
    // WEST — 10 bidirectional + 2 input + 2 DVDD + 2 DVSS
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_10 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_11 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_12 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_13 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_14 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_15 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_16 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_17 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_18 ();
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_19 ();
    (* keep *) gf180mcu_fd_io__in_s   pad_w_in_0  ();
    (* keep *) gf180mcu_fd_io__in_s   pad_w_in_1  ();
    (* keep *) gf180mcu_fd_io__dvdd   pad_w_dvdd_2 ();
    (* keep *) gf180mcu_fd_io__dvdd   pad_w_dvdd_3 ();
    (* keep *) gf180mcu_fd_io__dvss   pad_w_dvss_2 ();
    (* keep *) gf180mcu_fd_io__dvss   pad_w_dvss_3 ();

endmodule
