"""Exercise both logical blocks through the PDK's real IO-cell models."""
from pathlib import Path
import os,re,sys,subprocess
HERE=Path(__file__).resolve().parent
ws=HERE/'combined_padframe'
pdk=Path(os.environ.get('PDK_ROOT','/home/wlmoi/.volare'))/'gf180mcuD'
io=pdk/'libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v'
inputs=['clk','rst_n','uart_rx','fa_a','fa_b','fa_cin']
outputs=['uart_tx','fa_sum','fa_cout']
ports=[f'input wire {n}' for n in inputs]+[f'output wire {n}' for n in outputs]
text='module ChipOrchestraDualCorePads #(parameter UART_CLK_PER_BIT=87)(\n'+',\n'.join(ports)+'\n);\n'
text+='supply1 VDD, DVDD;\nsupply0 VSS, DVSS;\n'
text+='wire '+','.join('core_'+n for n in inputs+outputs)+';\n'
text+='ChipOrchestraDualCore #(.UART_CLK_PER_BIT(UART_CLK_PER_BIT)) u_core ('+','.join(f'.{n}(core_{n})' for n in inputs+outputs)+');\n'
for n in inputs:
 text+=f'gf180mcu_fd_io__in_c pad_{n} (.PAD({n}),.Y(core_{n}),.PU(1\'b0),.PD(1\'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));\n' if n!='uart_rx' else f'gf180mcu_fd_io__bi_t pad_{n} (.PAD({n}),.Y(core_{n}),.A(1\'b0),.IE(1\'b1),.OE(1\'b0),.PU(1\'b0),.PD(1\'b0),.CS(1\'b0),.SL(1\'b0),.PDRV0(1\'b0),.PDRV1(1\'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));\n'
for n in outputs:
 text+=f'gf180mcu_fd_io__bi_t pad_{n} (.PAD({n}),.A(core_{n}),.Y(),.IE(1\'b0),.OE(1\'b1),.PU(1\'b0),.PD(1\'b0),.CS(1\'b0),.SL(1\'b0),.PDRV0(1\'b0),.PDRV1(1\'b0),.VDD(VDD),.VSS(VSS),.DVDD(DVDD),.DVSS(DVSS));\n'
text+='endmodule\n'
(ws/'rtl/ChipOrchestraDualCorePads.v').write_text(text)
tb=(HERE/'cgra/tb/performance_tb.v').read_text().replace('module performance_tb;','module dual_pad_tb;')
old='NanoCGRA_Lite #(.UART_CLK_PER_BIT(CPB)) dut(.clk(clk),.rst_n(rst_n),.uart_rx(uart_rx),.uart_tx(uart_tx));'
new='''reg fa_a=0, fa_b=0, fa_cin=0;
wire fa_sum, fa_cout;
ChipOrchestraDualCorePads #(.UART_CLK_PER_BIT(CPB)) dut(.clk(clk),.rst_n(rst_n),.uart_rx(uart_rx),.uart_tx(uart_tx),.fa_a(fa_a),.fa_b(fa_b),.fa_cin(fa_cin),.fa_sum(fa_sum),.fa_cout(fa_cout));
integer fa_i;
initial begin
 for(fa_i=0;fa_i<8;fa_i=fa_i+1) begin
  {fa_a,fa_b,fa_cin}=fa_i; #20;
  if({fa_cout,fa_sum} !== ({1'b0,fa_a}+{1'b0,fa_b}+{1'b0,fa_cin})) $fatal(1,"FAIL fulladder through GF180 pads");
 end
 $display("TEST PASSED fulladder through GF180 pads checks=8");
end'''
assert old in tb
tb=tb.replace(old,new).replace('always @(posedge clk) begin','always @(posedge dut.core_clk) begin')
tb=tb.replace('dut.start_pulse','dut.u_core.u_cgra.start_pulse').replace('dut.c_done','dut.u_core.u_cgra.c_done')
(ws/'tb/dual_pad_tb.v').write_text(tb)
binary=ws/'reports/dual_pad_tb.vvp'
files=sorted((HERE/'cgra/rtl').glob('*.v'))+[HERE/'fulladder/rtl/fulladder.v',ws/'rtl/ChipOrchestraDualCore.v',ws/'rtl/ChipOrchestraDualCorePads.v',io,ws/'tb/dual_pad_tb.v']
compile=['iverilog','-g2012','-Dfunctional','-I',str(HERE/'cgra/rtl'),'-s','dual_pad_tb','-o',str(binary)]+[str(p) for p in files]
with (ws/'logs/pad_function_compile.log').open('w') as log:
 result=subprocess.run(compile,stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0,'Pad model compilation failed'
with (ws/'logs/pad_function_simulation.log').open('w') as log:
 result=subprocess.run(['vvp',str(binary)],stdout=log,stderr=subprocess.STDOUT,timeout=900)
log=(ws/'logs/pad_function_simulation.log').read_text()
assert result.returncode==0 and 'TEST PASSED checks=224' in log and 'checks=8' in log and 'FAIL' not in log,log[-3000:]
print('PAD FUNCTION PASSED: fulladder 8, CGRA 224, hardware UART divisor 87')
