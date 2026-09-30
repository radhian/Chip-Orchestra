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
    inout wire clk,     // physical clk pad (external side of pad_w_in_0)
    inout wire rst_n,   // physical rst_n pad (external side of pad_w_in_1)
    inout wire dout,    // physical output pad (external side of pad_e_bi_0)
    inout wire VDD,     // 5V supply ring (all pad VDD/DVDD pins, via dvdd pads)
    inout wire VSS      // ground ring (all pad VSS/DVSS pins, via dvss pads)
);

    // Core-side signals driven/received through the I/O pads.
    wire clk_core;
    wire rst_core;
    wire dout_core;

    // Core instance
    chip_core u_core (
        .clk(clk_core),
        .rst_n(rst_core),
        .dout(dout_core)
    );

    // NOTE: every pad/corner below carries the (* keep *) attribute.  Only
    // three pads carry signals (clk in, rst_n in, dout out); the rest are
    // unconnected in this workshop fixture.  Without (* keep *) Yosys would
    // optimise the unconnected pads away as dead cells and OpenROAD.PadRing
    // would fail with "No instance ... found".  (* keep *) forces synthesis to
    // preserve the physical instances so the pad ring can place them.

    // ---------------------------------------------------------------
    // Corner pads (4)
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__cor corner_sw (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__cor corner_se (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__cor corner_ne (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__cor corner_nw (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));

    // ---------------------------------------------------------------
    // SOUTH — 15 analog + 1 DVSS
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_0  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_1  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_2  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_3  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_4  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_5  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_6  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_7  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_8  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_9  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_10 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_11 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_12 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_13 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_s_analog_14 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__dvss     pad_s_dvss_0    (.DVDD(VDD), .DVSS(VSS), .VDD(VDD));

    // ---------------------------------------------------------------
    // EAST — 10 bidirectional + 1 DVDD + 1 DVSS
    // ---------------------------------------------------------------
    // dout leaves through this bidirectional pad in output mode (OE=1, IE=0):
    // core drives A, PAD is the external output.
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_0  (.A(dout_core), .PAD(dout), .OE(1'b1), .IE(1'b0), .CS(1'b0), .SL(1'b0), .PU(1'b0), .PD(1'b0), .DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_1  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_2  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_3  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_4  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_5  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_6  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_7  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_8  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_e_bi_9  (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__dvdd   pad_e_dvdd_0 (.DVDD(VDD), .DVSS(VSS), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__dvss   pad_e_dvss_1 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD));

    // ---------------------------------------------------------------
    // NORTH — 15 analog + 1 DVDD
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_15 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_16 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_17 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_18 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_19 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_20 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_21 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_22 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_23 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_24 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_25 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_26 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_27 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_28 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__asig_5p0 pad_n_analog_29 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__dvdd     pad_n_dvdd_1    (.DVDD(VDD), .DVSS(VSS), .VSS(VSS));

    // ---------------------------------------------------------------
    // WEST — 10 bidirectional + 2 input + 2 DVDD + 2 DVSS
    // ---------------------------------------------------------------
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_10 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_11 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_12 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_13 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_14 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_15 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_16 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_17 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_18 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__bi_24t pad_w_bi_19 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    // clk enters through this input pad: external clk -> PAD, Y -> core clock.
    (* keep *) gf180mcu_fd_io__in_s   pad_w_in_0  (.PAD(clk),   .Y(clk_core),  .PU(1'b0), .PD(1'b0), .DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    // rst_n enters through this input pad.
    (* keep *) gf180mcu_fd_io__in_s   pad_w_in_1  (.PAD(rst_n), .Y(rst_core),  .PU(1'b0), .PD(1'b0), .DVDD(VDD), .DVSS(VSS), .VDD(VDD), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__dvdd   pad_w_dvdd_2 (.DVDD(VDD), .DVSS(VSS), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__dvdd   pad_w_dvdd_3 (.DVDD(VDD), .DVSS(VSS), .VSS(VSS));
    (* keep *) gf180mcu_fd_io__dvss   pad_w_dvss_2 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD));
    (* keep *) gf180mcu_fd_io__dvss   pad_w_dvss_3 (.DVDD(VDD), .DVSS(VSS), .VDD(VDD));

endmodule
