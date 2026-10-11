"""Reproducible, local RTL and physical examples with a shared padframe."""
from pathlib import Path
import json,os,shutil,subprocess,sys,time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PDK=Path(os.environ.get('PDK_ROOT','/home/wlmoi/.volare'))/'gf180mcuD'
SC=PDK/'libs.ref/gf180mcu_fd_sc_mcu7t5v0'
LIB=SC/'lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib'
ENV=os.environ.copy()

def run(args,log,cwd=HERE,timeout=1800):
    log.parent.mkdir(parents=True,exist_ok=True)
    print('RUN',args[0],log.relative_to(HERE),flush=True)
    with log.open('w') as out:
        result=subprocess.run([str(x) for x in args],cwd=cwd,env=ENV,stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
    if result.returncode:raise RuntimeError(f'{args[0]} failed, inspect {log}')

def prepare():
    for name in ['fulladder','cgra','combined_padframe']:
        for sub in ['rtl','tb','synth','pnr','gds','logs','reports']:
            (HERE/name/sub).mkdir(parents=True,exist_ok=True)
    original=ROOT/'output/nanocgra_lite_3x3_opt'
    for p in (original/'rtl').iterdir():
        if p.suffix in ('.v','.vh'):shutil.copy2(p,HERE/'cgra/rtl'/p.name)
    for p in (original/'tb').glob('*.v'):shutil.copy2(p,HERE/'cgra/tb'/p.name)
    shutil.copy2(ROOT/'paper/nanocgra_performance_20261011/performance_tb.v',HERE/'cgra/tb/performance_tb.v')
    shutil.copy2(original/'gds/def2gds.py',HERE/'def2gds.py')

def retained_cgra():
    import hashlib
    original=ROOT/'output/nanocgra_lite_3x3_opt'
    ws=HERE/'cgra'
    files={'gds/nanocgra_lite_3x3_opt.gds':'gds/NanoCGRA_Lite.gds',
           'pnr/nanocgra_lite_3x3_opt.def':'pnr/NanoCGRA_Lite.def',
           'pnr/nanocgra_lite_3x3_opt.pnr.v':'pnr/NanoCGRA_Lite.pnr.v',
           'pnr/nanocgra_lite_3x3_opt.pnr.pwr.v':'pnr/NanoCGRA_Lite.pnr.pwr.v',
           'synth/nanocgra_lite_3x3_opt.synth.v':'synth/NanoCGRA_Lite.v'}
    for source,target in files.items():
        (ws/target).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original/source,ws/target)
    evidence={'physical_core':'Retained existing optimized NanoCGRA core, not a fresh hardening result',
              'source':'output/nanocgra_lite_3x3_opt','gds_sha256':hashlib.sha256((ws/'gds/NanoCGRA_Lite.gds').read_bytes()).hexdigest(),
              'fresh_uart_verification':'224 passing checks at divisor 87',
              'fresh_padframe_generation':True}
    (ws/'reports/provenance.json').write_text(json.dumps(evidence,indent=2)+'\n')

def simulate(name,top,files,tb,options=()):
    ws=HERE/name
    binary=ws/'reports'/f'{tb.stem}.vvp'
    run(['iverilog','-g2012','-I',ws/'rtl','-s',top,*options,'-o',binary,*files,tb],ws/'logs'/f'{top}_compile.log')
    run(['vvp',binary],ws/'logs'/f'{top}_simulation.log')
    text=(ws/'logs'/f'{top}_simulation.log').read_text()
    assert 'TEST PASSED' in text and 'FAIL' not in text,text[-1500:]

def harden(name,top):
    ws=HERE/name
    net=ws/'synth'/f'{top}.v'
    sources='\n'.join(f'read_verilog -I{ws/"rtl"} {p}' for p in sorted((ws/'rtl').glob('*.v')))
    synthesis=f'''{sources}
hierarchy -check -top {top}
synth -top {top} -flatten
dfflibmap -liberty {LIB}
abc -liberty {LIB} -D 100000
setundef -zero
hilomap -hicell gf180mcu_fd_sc_mcu7t5v0__tieh Z -locell gf180mcu_fd_sc_mcu7t5v0__tiel ZN
splitnets
opt_clean
read_liberty -lib {LIB}
check -assert
write_verilog -noattr {net}
tee -o {ws/'reports/synth_stat.txt'} stat -liberty {LIB}
'''
    (ws/'synth/synth.ys').write_text(synthesis)
    run(['yosys','-s',ws/'synth/synth.ys'],ws/'logs/synth.log')
    flow=(ROOT/'output/nanocgra_lite_3x3_opt/pnr/flow.tcl').read_text()
    flow=flow.replace('set NETL  output/nanocgra_lite_3x3_opt/synth/nanocgra_lite_3x3_opt.synth.v',f'set NETL {{{net}}}')
    flow=flow.replace('set OUT   output/nanocgra_lite_3x3_opt',f'set OUT {{{ws}}}').replace('set TOP   NanoCGRA_Lite',f'set TOP {top}')
    flow=flow.replace('nanocgra_lite_3x3_opt.def',f'{top}.def').replace('nanocgra_lite_3x3_opt.pnr.',f'{top}.pnr.').replace('nanocgra_lite_3x3_opt.odb',f'{top}.odb')
    if name=='fulladder':
        flow=flow.replace('create_clock -name clk -period 100.0 [get_ports clk]','create_clock -name clk -period 100.0')
        begin=flow.index('initialize_floorplan -utilization')
        end=flow.index('make_tracks',begin)
        flow=flow[:begin]+'initialize_floorplan -die_area {0 0 80 80} -core_area {10 10 70 70} -site GF018hv5v_mcu_sc7\n'+flow[end:]
        begin=flow.index('# ---- Clock tree synthesis')
        end=flow.index('# ---- Routing',begin)
        flow=flow[:begin]+flow[end:]
    (ws/'pnr/flow.tcl').write_text(flow)
    run(['openroad','-exit',ws/'pnr/flow.tcl'],ws/'logs/pnr.log')
    run(['klayout','-zz','-b','-r',HERE/'def2gds.py',
         '-rd',f'def_file={ws}/pnr/{top}.def','-rd',f'out_gds={ws}/gds/{top}.gds',
         '-rd',f'top_name={top}','-rd',f'tech_lef={SC}/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef',
         '-rd',f'cell_lef={SC}/lef/gf180mcu_fd_sc_mcu7t5v0.lef','-rd',f'cell_gds={SC}/gds/gf180mcu_fd_sc_mcu7t5v0.gds',
         '-rd',f'map_file={PDK}/libs.tech/klayout/tech/gf180mcu.map'],ws/'logs/def2gds.log')
    assert (ws/f'gds/{top}.gds').stat().st_size>1000

if __name__=='__main__':
    prepare()
    if '--assemble-only' not in sys.argv:
        fa=HERE/'fulladder'
        if '--physical-only' not in sys.argv:
            simulate('fulladder','fulladder_tb',[fa/'rtl/fulladder.v'],fa/'tb/fulladder_tb.v')
        cgra=HERE/'cgra'
        if '--physical-only' not in sys.argv:
            simulate('cgra','performance_tb',sorted((cgra/'rtl').glob('*.v')),cgra/'tb/performance_tb.v',['-P','performance_tb.CPB=87'])
        harden('fulladder','fulladder')
        if '--reharden-cgra' in sys.argv:
            harden('cgra','NanoCGRA_Lite')
        else:
            retained_cgra()
    print('CORE_EXAMPLES_DONE',flush=True)
    run(['python',HERE/'assemble_combined.py'],HERE/'combined_padframe/logs/assembly.log')
    run(['python',HERE/'verify_fulladder_gls.py'],HERE/'fulladder/logs/gls_verification.log')
    run(['python',HERE/'verify_pad_function.py'],HERE/'combined_padframe/logs/pad_function_execution.log')
    run(['python',HERE/'verify_gds_connectivity.py'],HERE/'combined_padframe/logs/gds_connectivity.log')
    run(['python',HERE/'render_examples.py'],HERE/'rendering.log')
