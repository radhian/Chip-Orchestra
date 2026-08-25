/// sta-blackbox
// Auto-generated blackbox interfaces for the GF180 gf180mcu_fd_io pad
// library.  DO NOT EDIT BY HAND — regenerate with strip_io_verilog.py.
// Only the module port interfaces are kept; internals are intentionally
// empty so Yosys and OpenSTA treat every pad cell as a blackbox.  The
// physical view comes from PAD_LEFS / PAD_GDS in librelane/config.yaml.

module gf180mcu_fd_io__asig_5p0 (ASIG5V, DVDD, DVSS, VDD, VSS);
	inout	ASIG5V;
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__bi_24t (CS, SL, IE, OE, PU, PD, A, PAD, Y, DVDD, DVSS, VDD, VSS);
	input	CS;
	input	SL;
	input	IE;
	input	OE;
	input	PU;
	input	PD;
	input	A;
	inout	PAD;
	output	Y;
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__bi_t (CS, SL, IE, OE, PU, PD, A, PDRV0, PDRV1, PAD, Y, DVDD, DVSS, VDD, VSS);
	input	CS;
	input	SL;
	input	IE;
	input	OE;
	input	PU;
	input	PD;
	input	A;
	input	PDRV0;
	input	PDRV1;
	inout	PAD;
	output	Y;
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__brk2 (VSS);
	inout	VSS;
endmodule

module gf180mcu_fd_io__brk5 (VSS);
	inout	VSS;
endmodule

module gf180mcu_fd_io__cor (DVDD, DVSS, VDD, VSS);
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__dvdd (DVDD, DVSS, VSS);
	inout	DVDD;
	inout	DVSS;
	inout	VSS;
endmodule

module gf180mcu_fd_io__dvss (DVDD, DVSS, VDD);
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
endmodule

module gf180mcu_fd_io__fill1 (DVDD, DVSS, VDD, VSS);
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__fill5 (DVDD, DVSS, VDD, VSS);
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__fill10 (DVDD, DVSS, VDD, VSS);
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__fillnc (DVDD, DVSS, VDD, VSS);
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__in_c (PU, PD, PAD, Y, DVDD, DVSS, VDD, VSS);
	input	PU;
	input	PD;
	input	PAD;
	output	Y;
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule

module gf180mcu_fd_io__in_s (PU, PD, PAD, Y, DVDD, DVSS, VDD, VSS);
	input	PU;
	input	PD;
	input	PAD;
	output	Y;
	inout	DVDD;
	inout	DVSS;
	inout	VDD;
	inout	VSS;
endmodule
