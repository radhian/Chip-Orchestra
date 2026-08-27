// ===== uart/rtl/rx.v =====
/* UART Receiver module 
 * Receives the serial signal on the rx pin.  Uses 4 posedge's
 * per baud bit to detect when the start bit comes.  Then every
 * 4 bits after that we shift in a sample to read our byte. 
 * Sets rdy output high after the byte is ready successfully. 
 *
 * Note, we dont really check that the stop bit goes high. 
 *
 * Has asynchronous reset. 
 */ 
module rx (
  input         res_n,
  input         rx,
  input         clk, /* Baud Rate x 4 (4 posedge's per bit) */
  output  [7:0] rx_byte,
  output        rdy
);

/* Count to 32 (8 bits x 4 samples )*/
reg       [4:0] count;
reg       [2:0] state;
reg       [2:0] state_nxt;

reg       [2:0] rx_shifter;
reg       [7:0] rx_byte_ff;
wire            rx_sample;

localparam WAIT = 3'b000,
           SNS1 = 3'b100,
           SNS2 = 3'b101,
           SNS3 = 3'b110,
           SNSX = 3'b111,
           READ = 3'b001,
           DONE = 3'b010;

/* When sampling RX if we got 2 highs in a row our sample 
   is high! */
assign rx_sample = (rx_shifter[2] && rx_shifter[1]) || 
                   (rx_shifter[1] && rx_shifter[0]);

assign rx_byte = rx_byte_ff;
assign rdy = state == DONE;

/* FSM Next State Derivation */
always @ (*)
begin
  case (state)
    WAIT: if (!rx)  /* As long was we are high stay waiting */
        state_nxt = SNS1;
      else          
        state_nxt = WAIT;
    SNS1: if (!rx)
        state_nxt = SNS2;
      else
        state_nxt = WAIT;
    SNS2: if (!rx)  /* If we get 4 lows in a row we got to read */
        state_nxt = SNSX;
      else
        state_nxt = WAIT;
    SNSX:
      state_nxt = READ;
    READ: if (count == 5'b11111) /* When read count is full, go back to wait */
        state_nxt = DONE;
      else
        state_nxt = READ;
    DONE:    state_nxt = WAIT;
    default: state_nxt = WAIT;
  endcase
end

/* Sense the start bit on posedge and negedge */
always @ (posedge clk or negedge res_n)
begin
   if (!res_n) 
    begin
      state <= WAIT;
      count <= 5'd0;
      rx_shifter <= 3'd0;
    end
   else
    begin
      state <= state_nxt;
      if (state == READ) begin
        rx_shifter <= {rx, rx_shifter[2:1]};
        count <= count + 1'b1;
      end
      else 
      begin
        rx_shifter <= 3'd0;
        count <= 5'd0;
      end
    end
end

/* If we are reading, stample the RX bits 
   every 3 samples shift it into RX byte */
always @ (posedge clk or negedge res_n)
begin
   if (!res_n) 
      rx_byte_ff <= 8'd0;
   else
     if ((state == READ) && count[1] && count[0])  /* When we are at count 3, sample the shift register */
       rx_byte_ff <= {rx_sample, rx_byte_ff[7:1]};
     else 
       rx_byte_ff <= rx_byte_ff;
end

endmodule


// ===== uart/rtl/tx.v =====
/* UART Transmitter module 
 * Transmits the bytes on tx_byte after stb signal goes high. 
 * Has asynchronous reset. 
 */ 
module tx (
  output          tx,
  input     [7:0] tx_byte,
  input           stb,   /* strobe tx_byte on posedge */
  input           res_n,
  input           clk    /* Baud Rate x 4 (same as rx) */ 
);

reg  [7:0] tx_byte_ff;    /* Clocked in byte to send out */
reg        stb_ff;        /* Indicator that the byte is ready to send */
reg  [2:0] bit_count;     /* Bit we are currently sending to TX when in SEND state */
reg  [1:0] baud_count, state, state_nxt;
reg        tx_ff;         /* The TX output register */

assign tx = tx_ff;

localparam WAIT = 3'b00,
           STRT = 3'b01,
           SEND = 3'b10,
           STOP = 3'b11;

/* Next state management */
always @(*)
begin
  case(state)
    WAIT:
      if (stb_ff)
        state_nxt = STRT; 
      else 
        state_nxt = WAIT;
    STRT:
      state_nxt = SEND;
    SEND:
      if (bit_count == 3'b111)
        state_nxt = STOP;
      else
        state_nxt = SEND;
    STOP:
      state_nxt = WAIT;
    default: state_nxt = WAIT;
  endcase
      
end

/* TX bits go out when the state changes */
always @(*)
case(state)
  STRT:    tx_ff = 1'b0;
  SEND:    tx_ff = tx_byte_ff[bit_count];
  STOP:    tx_ff = 1'b1;
  default: tx_ff = 1'b1;
endcase

/* Strobing in the tx_byte so we dont lose it */
always @(posedge clk or negedge res_n)
begin
  if (!res_n)
  begin
    tx_byte_ff <= 8'h00;
    stb_ff <= 1'b0;
  end
  else
  begin
    if ((state == WAIT) && !stb_ff) /* If we are waiting for the stb_ff and its not on turn it on*/
      stb_ff <= stb; 
    else if (state != WAIT) /* If we are done waiting we can turn off */ 
      stb_ff <= stb;
    else                    /* Otherwise maintain state */
      stb_ff <= stb_ff; 
      
    if (stb) /* strobe in the input on the stb signal */
      tx_byte_ff <= tx_byte;
    else 
      tx_byte_ff <= tx_byte_ff;

  end
end

/* Clock devider. We watch the 3rd bit of this counter
   to generate the baud rate clock 
 */
always @(posedge clk or negedge res_n)
begin
  if (!res_n)
    baud_count <= 2'h0;
  else
    baud_count <= baud_count + 1'b1;

end

/* State management block. Doing a few things here:
 *  - Do the state transition 
 *  - Keep track of the BIT count when we are in the SEND phase
 */
always @(posedge baud_count[1] or negedge res_n)
begin
  if (!res_n)
  begin
    bit_count <= 3'h0;
    state <= WAIT;
  end
  else
  begin
    state <= state_nxt;
    
   if (state == SEND)
     bit_count <= bit_count + 1'b1;
   else 
     bit_count <= 3'h0;
  end
end
    
endmodule

// ===== uart/rtl/pll9600.v =====
// megafunction wizard: %ALTPLL%
// GENERATION: STANDARD
// VERSION: WM1.0
// MODULE: altpll 

// ============================================================
// File Name: pll9600.v
// Megafunction Name(s):
// 			altpll
//
// Simulation Library Files(s):
// 			altera_mf
// ============================================================
// ************************************************************
// THIS IS A WIZARD-GENERATED FILE. DO NOT EDIT THIS FILE!
//
// 14.0.0 Build 200 06/17/2014 SJ Web Edition
// ************************************************************


//Copyright (C) 1991-2014 Altera Corporation. All rights reserved.
//Your use of Altera Corporation's design tools, logic functions 
//and other software and tools, and its AMPP partner logic 
//functions, and any output files from any of the foregoing 
//(including device programming or simulation files), and any 
//associated documentation or information are expressly subject 
//to the terms and conditions of the Altera Program License 
//Subscription Agreement, the Altera Quartus II License Agreement,
//the Altera MegaCore Function License Agreement, or other 
//applicable license agreement, including, without limitation, 
//that your use is for the sole purpose of programming logic 
//devices manufactured by Altera and sold by Altera or its 
//authorized distributors.  Please refer to the applicable 
//agreement for further details.


// synopsys translate_off
`timescale 1 ps / 1 ps
// synopsys translate_on
module pll9600 (
	inclk0,
	c0);

	input	  inclk0;
	output	  c0;

	wire [0:0] sub_wire2 = 1'h0;
	wire [4:0] sub_wire3;
	wire  sub_wire0 = inclk0;
	wire [1:0] sub_wire1 = {sub_wire2, sub_wire0};
	wire [0:0] sub_wire4 = sub_wire3[0:0];
	wire  c0 = sub_wire4;

	altpll	altpll_component (
				.inclk (sub_wire1),
				.clk (sub_wire3),
				.activeclock (),
				.areset (1'b0),
				.clkbad (),
				.clkena ({6{1'b1}}),
				.clkloss (),
				.clkswitch (1'b0),
				.configupdate (1'b0),
				.enable0 (),
				.enable1 (),
				.extclk (),
				.extclkena ({4{1'b1}}),
				.fbin (1'b1),
				.fbmimicbidir (),
				.fbout (),
				.fref (),
				.icdrclk (),
				.locked (),
				.pfdena (1'b1),
				.phasecounterselect ({4{1'b1}}),
				.phasedone (),
				.phasestep (1'b1),
				.phaseupdown (1'b1),
				.pllena (1'b1),
				.scanaclr (1'b0),
				.scanclk (1'b0),
				.scanclkena (1'b1),
				.scandata (1'b0),
				.scandataout (),
				.scandone (),
				.scanread (1'b0),
				.scanwrite (1'b0),
				.sclkout0 (),
				.sclkout1 (),
				.vcooverrange (),
				.vcounderrange ());
	defparam
		altpll_component.bandwidth_type = "AUTO",
		altpll_component.clk0_divide_by = 15625,
		altpll_component.clk0_duty_cycle = 50,
		altpll_component.clk0_multiply_by = 12,
		altpll_component.clk0_phase_shift = "0",
		altpll_component.compensate_clock = "CLK0",
		altpll_component.inclk0_input_frequency = 20000,
		altpll_component.intended_device_family = "Cyclone IV E",
		altpll_component.lpm_hint = "CBX_MODULE_PREFIX=pll9600",
		alt

// ===== uart/rtl/pll115200.v =====
// megafunction wizard: %ALTPLL%
// GENERATION: STANDARD
// VERSION: WM1.0
// MODULE: altpll 

// ============================================================
// File Name: pll115200.v
// Megafunction Name(s):
// 			altpll
//
// Simulation Library Files(s):
// 			altera_mf
// ============================================================
// ************************************************************
// THIS IS A WIZARD-GENERATED FILE. DO NOT EDIT THIS FILE!
//
// 14.0.0 Build 200 06/17/2014 SJ Web Edition
// *********************************