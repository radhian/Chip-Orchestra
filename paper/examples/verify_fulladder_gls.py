from pathlib import Path
import os,subprocess
HERE=Path(__file__).resolve().parent
ws=HERE/'fulladder'
sc=Path(os.environ.get('PDK_ROOT','/home/wlmoi/.volare'))/'gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog'
binary=ws/'reports/fulladder_gls.vvp'
args=['iverilog','-g2012','-DFUNCTIONAL','-s','fulladder_tb','-o',str(binary),str(ws/'tb/fulladder_tb.v'),str(sc/'gf180mcu_fd_sc_mcu7t5v0.v'),str(sc/'primitives.v'),str(ws/'pnr/fulladder.pnr.v')]
with (ws/'logs/gls_compile.log').open('w') as log:
 result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0
with (ws/'logs/gls_simulation.log').open('w') as log:
 result=subprocess.run(['vvp',str(binary)],stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0
assert 'TEST PASSED' in (ws/'logs/gls_simulation.log').read_text()
print('POST-ROUTE FULLADDER PASSED all eight input combinations')
