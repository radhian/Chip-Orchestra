`timescale 1ns/1ps
module performance_tb;
parameter CPB = 87;
localparam integer BITT = CPB * 100;
reg clk=0, rst_n=0, uart_rx=1;
wire uart_tx;
always #50 clk=~clk;
NanoCGRA_Lite #(.UART_CLK_PER_BIT(CPB)) dut(.clk(clk),.rst_n(rst_n),.uart_rx(uart_rx),.uart_tx(uart_tx));
integer errors=0, checks=0, cycle=0, accept_cycle=0, core_cycles=0;
reg old_done=0;
always @(posedge clk) begin
    cycle=cycle+1;
    if(rst_n && dut.start_pulse) accept_cycle=cycle;
    #1;
    if(rst_n && dut.c_done && !old_done) core_cycles=cycle-accept_cycle;
    old_done=dut.c_done;
end
initial begin #2000000000; $fatal(1,"TEST FAILED watchdog"); end
task send_byte(input [7:0] b);
integer i;
begin
 uart_rx=0; #(BITT);
 for(i=0;i<8;i=i+1) begin uart_rx=b[i]; #(BITT); end
 uart_rx=1; #(2*BITT);
end endtask
task packet(input [7:0] cmd,addr,data);
begin send_byte(cmd);send_byte(addr);send_byte(data);end endtask
task receive(output [7:0] b);
integer i;
begin
 @(negedge uart_tx); #(BITT+BITT/2);
 for(i=0;i<8;i=i+1) begin b[i]=uart_tx; #(BITT);end
 #(BITT/2);
end endtask
task run_op(input integer id,input [7:0] op,a,b,expected);
reg [7:0] observed;
time started,run_started,read_started,finished;
begin
 started=$time;
 packet(1,0,a);packet(1,1,b);packet(1,8'h90,op);
 packet(1,8'h99,0);packet(1,8'h9a,1);packet(1,8'h9b,8'h10);
 run_started=$time;packet(3,0,1);
 repeat(200) @(posedge clk);
 read_started=$time;
 fork
  begin packet(2,8'h10,0); end
  begin receive(observed); end
 join
 finished=$time;
 checks=checks+1;
 if(observed !== expected || core_cycles != 5) begin
  errors=errors+1;
  $display("FAIL id=%0d op=%0d expected=%0d observed=%0d core_cycles=%0d",id,op,expected,observed,core_cycles);
 end
 $display("MEASURE id=%0d op=%0d expected=%0d observed=%0d total_ns=%0d run_read_ns=%0d read_ns=%0d core_cycles=%0d",id,op,expected,observed,finished-started,finished-run_started,finished-read_started,core_cycles);
end endtask
integer addr;
reg [7:0] rd;
initial begin
 repeat(5) @(negedge clk);rst_n=1;repeat(5) @(negedge clk);
 for(addr=0;addr<32;addr=addr+1) begin
  packet(1,addr,(addr*37+11)&255);
  fork
   begin packet(2,addr,0); end
   begin receive(rd); end
  join
  checks=checks+1;
  if(rd !== ((addr*37+11)&255)) begin errors=errors+1;$display("FAIL SRAM address=%0d observed=%0d",addr,rd);end
 end
        run_op(0, 8'd0, 8'd0, 8'd0, 8'd0);
        run_op(1, 8'd0, 8'd0, 8'd255, 8'd255);
        run_op(2, 8'd0, 8'd255, 8'd0, 8'd255);
        run_op(3, 8'd0, 8'd255, 8'd255, 8'd254);
        run_op(4, 8'd0, 8'd127, 8'd128, 8'd255);
        run_op(5, 8'd0, 8'd128, 8'd127, 8'd255);
        run_op(6, 8'd0, 8'd1, 8'd255, 8'd0);
        run_op(7, 8'd0, 8'd255, 8'd1, 8'd0);
        run_op(8, 8'd0, 8'd251, 8'd177, 8'd172);
        run_op(9, 8'd0, 8'd253, 8'd173, 8'd170);
        run_op(10, 8'd0, 8'd142, 8'd28, 8'd170);
        run_op(11, 8'd0, 8'd20, 8'd183, 8'd203);
        run_op(12, 8'd0, 8'd245, 8'd19, 8'd8);
        run_op(13, 8'd0, 8'd7, 8'd176, 8'd183);
        run_op(14, 8'd0, 8'd111, 8'd65, 8'd176);
        run_op(15, 8'd0, 8'd241, 8'd13, 8'd254);
        run_op(16, 8'd0, 8'd1, 8'd117, 8'd118);
        run_op(17, 8'd0, 8'd123, 8'd77, 8'd200);
        run_op(18, 8'd0, 8'd99, 8'd189, 8'd32);
        run_op(19, 8'd0, 8'd232, 8'd149, 8'd125);
        run_op(20, 8'd0, 8'd8, 8'd71, 8'd79);
        run_op(21, 8'd0, 8'd131, 8'd213, 8'd88);
        run_op(22, 8'd0, 8'd179, 8'd103, 8'd26);
        run_op(23, 8'd0, 8'd155, 8'd113, 8'd12);
        run_op(24, 8'd1, 8'd0, 8'd0, 8'd0);
        run_op(25, 8'd1, 8'd0, 8'd255, 8'd1);
        run_op(26, 8'd1, 8'd255, 8'd0, 8'd255);
        run_op(27, 8'd1, 8'd255, 8'd255, 8'd0);
        run_op(28, 8'd1, 8'd127, 8'd128, 8'd255);
        run_op(29, 8'd1, 8'd128, 8'd127, 8'd1);
        run_op(30, 8'd1, 8'd1, 8'd255, 8'd2);
        run_op(31, 8'd1, 8'd255, 8'd1, 8'd254);
        run_op(32, 8'd1, 8'd251, 8'd177, 8'd74);
        run_op(33, 8'd1, 8'd253, 8'd173, 8'd80);
        run_op(34, 8'd1, 8'd142, 8'd28, 8'd114);
        run_op(35, 8'd1, 8'd20, 8'd183, 8'd93);
        run_op(36, 8'd1, 8'd245, 8'd19, 8'd226);
        run_op(37, 8'd1, 8'd7, 8'd176, 8'd87);
        run_op(38, 8'd1, 8'd111, 8'd65, 8'd46);
        run_op(39, 8'd1, 8'd241, 8'd13, 8'd228);
        run_op(40, 8'd1, 8'd1, 8'd117, 8'd140);
        run_op(41, 8'd1, 8'd123, 8'd77, 8'd46);
        run_op(42, 8'd1, 8'd99, 8'd189, 8'd166);
        run_op(43, 8'd1, 8'd232, 8'd149, 8'd83);
        run_op(44, 8'd1, 8'd8, 8'd71, 8'd193);
        run_op(45, 8'd1, 8'd131, 8'd213, 8'd174);
        run_op(46, 8'd1, 8'd179, 8'd103, 8'd76);
        run_op(47, 8'd1, 8'd155, 8'd113, 8'd42);
        run_op(48, 8'd2, 8'd0, 8'd0, 8'd0);
        run_op(49, 8'd2, 8'd0, 8'd255, 8'd0);
        run_op(50, 8'd2, 8'd255, 8'd0, 8'd0);
        run_op(51, 8'd2, 8'd255, 8'd255, 8'd255);
        run_op(52, 8'd2, 8'd127, 8'd128, 8'd0);
        run_op(53, 8'd2, 8'd128, 8'd127, 8'd0);
        run_op(54, 8'd2, 8'd1, 8'd255, 8'd1);
        run_op(55, 8'd2, 8'd255, 8'd1, 8'd1);
        run_op(56, 8'd2, 8'd251, 8'd177, 8'd177);
        run_op(57, 8'd2, 8'd253, 8'd173, 8'd173);
        run_op(58, 8'd2, 8'd142, 8'd28, 8'd12);
        run_op(59, 8'd2, 8'd20, 8'd183, 8'd20);
        run_op(60, 8'd2, 8'd245, 8'd19, 8'd17);
        run_op(61, 8'd2, 8'd7, 8'd176, 8'd0);
        run_op(62, 8'd2, 8'd111, 8'd65, 8'd65);
        run_op(63, 8'd2, 8'd241, 8'd13, 8'd1);
        run_op(64, 8'd2, 8'd1, 8'd117, 8'd1);
        run_op(65, 8'd2, 8'd123, 8'd77, 8'd73);
        run_op(66, 8'd2, 8'd99, 8'd189, 8'd33);
        run_op(67, 8'd2, 8'd232, 8'd149, 8'd128);
        run_op(68, 8'd2, 8'd8, 8'd71, 8'd0);
        run_op(69, 8'd2, 8'd131, 8'd213, 8'd129);
        run_op(70, 8'd2, 8'd179, 8'd103, 8'd35);
        run_op(71, 8'd2, 8'd155, 8'd113, 8'd17);
        run_op(72, 8'd3, 8'd0, 8'd0, 8'd0);
        run_op(73, 8'd3, 8'd0, 8'd255, 8'd255);
        run_op(74, 8'd3, 8'd255, 8'd0, 8'd255);
        run_op(75, 8'd3, 8'd255, 8'd255, 8'd255);
        run_op(76, 8'd3, 8'd127, 8'd128, 8'd255);
        run_op(77, 8'd3, 8'd128, 8'd127, 8'd255);
        run_op(78, 8'd3, 8'd1, 8'd255, 8'd255);
        run_op(79, 8'd3, 8'd255, 8'd1, 8'd255);
        run_op(80, 8'd3, 8'd251, 8'd177, 8'd251);
        run_op(81, 8'd3, 8'd253, 8'd173, 8'd253);
        run_op(82, 8'd3, 8'd142, 8'd28, 8'd158);
        run_op(83, 8'd3, 8'd20, 8'd183, 8'd183);
        run_op(84, 8'd3, 8'd245, 8'd19, 8'd247);
        run_op(85, 8'd3, 8'd7, 8'd176, 8'd183);
        run_op(86, 8'd3, 8'd111, 8'd65, 8'd111);
        run_op(87, 8'd3, 8'd241, 8'd13, 8'd253);
        run_op(88, 8'd3, 8'd1, 8'd117, 8'd117);
        run_op(89, 8'd3, 8'd123, 8'd77, 8'd127);
        run_op(90, 8'd3, 8'd99, 8'd189, 8'd255);
        run_op(91, 8'd3, 8'd232, 8'd149, 8'd253);
        run_op(92, 8'd3, 8'd8, 8'd71, 8'd79);
        run_op(93, 8'd3, 8'd131, 8'd213, 8'd215);
        run_op(94, 8'd3, 8'd179, 8'd103, 8'd247);
        run_op(95, 8'd3, 8'd155, 8'd113, 8'd251);
        run_op(96, 8'd4, 8'd0, 8'd0, 8'd0);
        run_op(97, 8'd4, 8'd0, 8'd255, 8'd255);
        run_op(98, 8'd4, 8'd255, 8'd0, 8'd255);
        run_op(99, 8'd4, 8'd255, 8'd255, 8'd0);
        run_op(100, 8'd4, 8'd127, 8'd128, 8'd255);
        run_op(101, 8'd4, 8'd128, 8'd127, 8'd255);
        run_op(102, 8'd4, 8'd1, 8'd255, 8'd254);
        run_op(103, 8'd4, 8'd255, 8'd1, 8'd254);
        run_op(104, 8'd4, 8'd251, 8'd177, 8'd74);
        run_op(105, 8'd4, 8'd253, 8'd173, 8'd80);
        run_op(106, 8'd4, 8'd142, 8'd28, 8'd146);
        run_op(107, 8'd4, 8'd20, 8'd183, 8'd163);
        run_op(108, 8'd4, 8'd245, 8'd19, 8'd230);
        run_op(109, 8'd4, 8'd7, 8'd176, 8'd183);
        run_op(110, 8'd4, 8'd111, 8'd65, 8'd46);
        run_op(111, 8'd4, 8'd241, 8'd13, 8'd252);
        run_op(112, 8'd4, 8'd1, 8'd117, 8'd116);
        run_op(113, 8'd4, 8'd123, 8'd77, 8'd54);
        run_op(114, 8'd4, 8'd99, 8'd189, 8'd222);
        run_op(115, 8'd4, 8'd232, 8'd149, 8'd125);
        run_op(116, 8'd4, 8'd8, 8'd71, 8'd79);
        run_op(117, 8'd4, 8'd131, 8'd213, 8'd86);
        run_op(118, 8'd4, 8'd179, 8'd103, 8'd212);
        run_op(119, 8'd4, 8'd155, 8'd113, 8'd234);
        run_op(120, 8'd5, 8'd0, 8'd0, 8'd0);
        run_op(121, 8'd5, 8'd0, 8'd255, 8'd0);
        run_op(122, 8'd5, 8'd255, 8'd0, 8'd0);
        run_op(123, 8'd5, 8'd255, 8'd255, 8'd1);
        run_op(124, 8'd5, 8'd127, 8'd128, 8'd128);
        run_op(125, 8'd5, 8'd128, 8'd127, 8'd128);
        run_op(126, 8'd5, 8'd1, 8'd255, 8'd255);
        run_op(127, 8'd5, 8'd255, 8'd1, 8'd255);
        run_op(128, 8'd5, 8'd251, 8'd177, 8'd139);
        run_op(129, 8'd5, 8'd253, 8'd173, 8'd249);
        run_op(130, 8'd5, 8'd142, 8'd28, 8'd136);
        run_op(131, 8'd5, 8'd20, 8'd183, 8'd76);
        run_op(132, 8'd5, 8'd245, 8'd19, 8'd47);
        run_op(133, 8'd5, 8'd7, 8'd176, 8'd208);
        run_op(134, 8'd5, 8'd111, 8'd65, 8'd47);
        run_op(135, 8'd5, 8'd241, 8'd13, 8'd61);
        run_op(136, 8'd5, 8'd1, 8'd117, 8'd117);
        run_op(137, 8'd5, 8'd123, 8'd77, 8'd255);
        run_op(138, 8'd5, 8'd99, 8'd189, 8'd23);
        run_op(139, 8'd5, 8'd232, 8'd149, 8'd8);
        run_op(140, 8'd5, 8'd8, 8'd71, 8'd56);
        run_op(141, 8'd5, 8'd131, 8'd213, 8'd255);
        run_op(142, 8'd5, 8'd179, 8'd103, 8'd5);
        run_op(143, 8'd5, 8'd155, 8'd113, 8'd107);
        run_op(144, 8'd6, 8'd0, 8'd0, 8'd0);
        run_op(145, 8'd6, 8'd0, 8'd255, 8'd0);
        run_op(146, 8'd6, 8'd255, 8'd0, 8'd0);
        run_op(147, 8'd6, 8'd255, 8'd255, 8'd1);
        run_op(148, 8'd6, 8'd127, 8'd128, 8'd128);
        run_op(149, 8'd6, 8'd128, 8'd127, 8'd128);
        run_op(150, 8'd6, 8'd1, 8'd255, 8'd255);
        run_op(151, 8'd6, 8'd255, 8'd1, 8'd255);
        run_op(152, 8'd6, 8'd251, 8'd177, 8'd139);
        run_op(153, 8'd6, 8'd253, 8'd173, 8'd249);
        run_op(154, 8'd6, 8'd142, 8'd28, 8'd136);
        run_op(155, 8'd6, 8'd20, 8'd183, 8'd76);
        run_op(156, 8'd6, 8'd245, 8'd19, 8'd47);
        run_op(157, 8'd6, 8'd7, 8'd176, 8'd208);
        run_op(158, 8'd6, 8'd111, 8'd65, 8'd47);
        run_op(159, 8'd6, 8'd241, 8'd13, 8'd61);
        run_op(160, 8'd6, 8'd1, 8'd117, 8'd117);
        run_op(161, 8'd6, 8'd123, 8'd77, 8'd255);
        run_op(162, 8'd6, 8'd99, 8'd189, 8'd23);
        run_op(163, 8'd6, 8'd232, 8'd149, 8'd8);
        run_op(164, 8'd6, 8'd8, 8'd71, 8'd56);
        run_op(165, 8'd6, 8'd131, 8'd213, 8'd255);
        run_op(166, 8'd6, 8'd179, 8'd103, 8'd5);
        run_op(167, 8'd6, 8'd155, 8'd113, 8'd107);
        run_op(168, 8'd7, 8'd0, 8'd0, 8'd0);
        run_op(169, 8'd7, 8'd0, 8'd255, 8'd0);
        run_op(170, 8'd7, 8'd255, 8'd0, 8'd255);
        run_op(171, 8'd7, 8'd255, 8'd255, 8'd255);
        run_op(172, 8'd7, 8'd127, 8'd128, 8'd127);
        run_op(173, 8'd7, 8'd128, 8'd127, 8'd128);
        run_op(174, 8'd7, 8'd1, 8'd255, 8'd1);
        run_op(175, 8'd7, 8'd255, 8'd1, 8'd255);
        run_op(176, 8'd7, 8'd251, 8'd177, 8'd251);
        run_op(177, 8'd7, 8'd253, 8'd173, 8'd253);
        run_op(178, 8'd7, 8'd142, 8'd28, 8'd142);
        run_op(179, 8'd7, 8'd20, 8'd183, 8'd20);
        run_op(180, 8'd7, 8'd245, 8'd19, 8'd245);
        run_op(181, 8'd7, 8'd7, 8'd176, 8'd7);
        run_op(182, 8'd7, 8'd111, 8'd65, 8'd111);
        run_op(183, 8'd7, 8'd241, 8'd13, 8'd241);
        run_op(184, 8'd7, 8'd1, 8'd117, 8'd1);
        run_op(185, 8'd7, 8'd123, 8'd77, 8'd123);
        run_op(186, 8'd7, 8'd99, 8'd189, 8'd99);
        run_op(187, 8'd7, 8'd232, 8'd149, 8'd232);
        run_op(188, 8'd7, 8'd8, 8'd71, 8'd8);
        run_op(189, 8'd7, 8'd131, 8'd213, 8'd131);
        run_op(190, 8'd7, 8'd179, 8'd103, 8'd179);
        run_op(191, 8'd7, 8'd155, 8'd113, 8'd155);
 if(errors) $fatal(1,"TEST FAILED errors=%0d checks=%0d",errors,checks);
 $display("TEST PASSED checks=%0d vectors=192 CPB=%0d",checks,CPB);
 $finish;
end
endmodule
