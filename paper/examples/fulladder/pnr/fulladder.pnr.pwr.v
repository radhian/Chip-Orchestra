module fulladder (a,
    b,
    cin,
    cout,
    sum);
 input a;
 input b;
 input cin;
 output cout;
 output sum;

 wire _0_;
 wire _1_;
 wire VDD;
 wire VSS;

 gf180mcu_fd_sc_mcu7t5v0__nand2_1 _2_ (.A1(b),
    .A2(cin),
    .ZN(_0_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__xor3_2 _3_ (.A1(b),
    .A2(a),
    .A3(cin),
    .Z(sum),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__oai21_2 _4_ (.A1(b),
    .A2(cin),
    .B(a),
    .ZN(_1_),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__nand2_4 _5_ (.A1(_0_),
    .A2(_1_),
    .ZN(cout),
    .VDD(VDD),
    .VNW(VDD),
    .VPW(VSS),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_0_Right_0 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_1_Right_1 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_2_Right_2 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_3_Right_3 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_4_Right_4 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_5_Right_5 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_6_Right_6 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_7_Right_7 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_8_Right_8 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_9_Right_9 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_10_Right_10 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_11_Right_11 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_12_Right_12 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_13_Right_13 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_0_Left_14 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_1_Left_15 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_2_Left_16 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_3_Left_17 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_4_Left_18 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_5_Left_19 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_6_Left_20 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_7_Left_21 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_8_Left_22 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_9_Left_23 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_10_Left_24 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_11_Left_25 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_12_Left_26 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__endcap PHY_EDGE_ROW_13_Left_27 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_28 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_29 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_0_30 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_1_31 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_2_32 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_3_33 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_4_34 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_5_35 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_6_36 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_7_37 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_8_38 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_9_39 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_10_40 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_11_41 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_12_42 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_13_43 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_13_44 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__filltie TAP_TAPCELL_ROW_13_45 (.VDD(VDD),
    .VSS(VSS));
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_0_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_8 FILLER_0_0_36 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_0_0_44 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_0_67 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_0_70 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_0_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_1_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_1_34 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_2 FILLER_0_1_38 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_1_40 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_1_72 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_1_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_2_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_2_34 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_8 FILLER_0_2_37 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_2_45 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_2_64 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_8 FILLER_0_2_96 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_2_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_3_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_3_66 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_3_72 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_3_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_4_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_4_34 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_4_37 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_4_101 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_5_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_5_66 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_5_72 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_5_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_6_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_6_34 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_6_37 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_6_101 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_7_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_7_66 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_7_72 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_7_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_8_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_8_34 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_8_37 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_8_101 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_9_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_9_66 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_9_72 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_9_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_10_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_10_34 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_10_37 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_10_101 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_11_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_11_66 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_11_72 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_11_104 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_12_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_12_34 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_64 FILLER_0_12_37 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_4 FILLER_0_12_101 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_13_2 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_13_36 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_32 FILLER_0_13_70 ();
 gf180mcu_fd_sc_mcu7t5v0__fill_1 FILLER_0_13_104 ();
endmodule
