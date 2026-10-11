"""Independent arithmetic vectors and timing instrumentation for NanoCGRA."""
import json
import random
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WS = ROOT / "paper" / "nanocgra_performance_20261011"
WS.mkdir(exist_ok=True)
RTL = ROOT / "paper" / "nanocgra_e2e_20261011" / "rtl"
rng = random.Random(20261011)
pairs = [(0, 0), (0, 255), (255, 0), (255, 255), (127, 128), (128, 127), (1, 255), (255, 1)]
pairs += [(rng.randrange(256), rng.randrange(256)) for _ in range(16)]
vectors = []
for op in range(8):
    for a, b in pairs:
        expected = [a + b, a - b, a & b, a | b, a ^ b, a * b, a * b, a][op] & 255
        vectors.append((op, a, b, expected))
(WS / "vectors.json").write_text(json.dumps({"seed": 20261011, "vectors": vectors}, indent=2))
calls = "\n".join(f"        run_op({i}, 8'd{op}, 8'd{a}, 8'd{b}, 8'd{exp});" for i, (op,a,b,exp) in enumerate(vectors))
tb = r'''`timescale 1ns/1ps
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
__CALLS__
 if(errors) $fatal(1,"TEST FAILED errors=%0d checks=%0d",errors,checks);
 $display("TEST PASSED checks=%0d vectors=192 CPB=%0d",checks,CPB);
 $finish;
end
endmodule
'''.replace("__CALLS__", calls)
(WS / "performance_tb.v").write_text(tb)
results = json.loads((WS/"performance_results.json").read_text()) if (WS/"performance_results.json").exists() else {}
for cpb in [8,87]:
    compile_cmd = ["iverilog","-g2012","-I",str(RTL),"-s","performance_tb","-P",f"performance_tb.CPB={cpb}","-o",str(WS/f"performance_{cpb}.vvp")]
    compile_cmd += [str(p) for p in sorted(RTL.glob("*.v"))] + [str(WS/"performance_tb.v")]
    c = subprocess.run(compile_cmd,capture_output=True,text=True)
    (WS/f"compile_{cpb}.log").write_text(c.stdout+c.stderr)
    if c.returncode: raise RuntimeError(c.stderr)
    sim = subprocess.run(["vvp",str(WS/f"performance_{cpb}.vvp")],capture_output=True,text=True,timeout=900)
    (WS/f"simulation_{cpb}.log").write_text(sim.stdout+sim.stderr)
    rows = [{k:int(v) for k,v in re.findall(r"(\w+)=([0-9]+)",line)} for line in sim.stdout.splitlines() if line.startswith("MEASURE")]
    summary = {"cpb":cpb,"clock_hz":10_000_000,"baud":10_000_000/cpb,"returncode":sim.returncode,
               "passed":sim.returncode==0 and "TEST PASSED" in sim.stdout,"vectors":len(rows),"sram_checks":32,
               "latency_definition":"First operand-write start bit to completion of returned result byte, including six writes, RUN, 200-cycle host wait, READ, and UART response",
               "timing":{},"measurements":rows}
    for key in ["total_ns","run_read_ns","read_ns","core_cycles"]:
        vals=[r[key] for r in rows]
        summary["timing"][key]={"min":min(vals),"max":max(vals),"mean":sum(vals)/len(vals)}
    summary["sequential_result_rate_per_s"] = 1e9 / summary["timing"]["total_ns"]["mean"]
    summary["raw_uart_bytes_per_s_upper_bound"] = 10_000_000/(10*cpb)
    results[str(cpb)] = summary
    print(json.dumps({k:v for k,v in summary.items() if k!="measurements"}),flush=True)
    (WS/"performance_results.json").write_text(json.dumps(results,indent=2))
    if not summary["passed"]: raise RuntimeError("Simulation failed, see log")
