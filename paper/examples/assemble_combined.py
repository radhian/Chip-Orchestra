from pathlib import Path
import json,os,sys,shutil
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'eda-service'))
from toolchain import padring_runner
from toolchain.pin_assembly import assemble
ws=HERE/'combined_padframe'
manifest={'top':'ChipOrchestraDualCore_chip','pdk_root':os.environ.get('PDK_ROOT','/home/wlmoi/.volare'),
          'cores':[{'instance':'u_cgra','top':'NanoCGRA_Lite','gds':'../cgra/gds/NanoCGRA_Lite.gds','def':'../cgra/pnr/NanoCGRA_Lite.def','origin_um':[1170,1250]},
                   {'instance':'u_fulladder','top':'fulladder','gds':'../fulladder/gds/fulladder.gds','def':'../fulladder/pnr/fulladder.def','origin_um':[1880,1430]}],
          'connections':[]}
for net,instance,pin,direction,pad in [('clk','u_cgra','clk','INPUT',346),('rst_n','u_cgra','rst_n','INPUT',345),
    ('uart_rx','u_cgra','uart_rx','INPUT',315),('uart_tx','u_cgra','uart_tx','OUTPUT',316),
    ('fa_a','u_fulladder','a','INPUT',337),('fa_b','u_fulladder','b','INPUT',338),('fa_cin','u_fulladder','cin','INPUT',334),
    ('fa_sum','u_fulladder','sum','OUTPUT',328),('fa_cout','u_fulladder','cout','OUTPUT',326)]:
    manifest['connections'].append({'net':net,'core':instance,'pin':pin,'direction':direction,'pad_reference':pad})
if '--probe' in sys.argv:
    ws=ws/'probe'
    for sub in ['logs','reports','gds','padring']: (ws/sub).mkdir(parents=True,exist_ok=True)
    manifest['cores'][0]['gds']=str(ROOT/'output/nanocgra_lite_3x3_opt/gds/nanocgra_lite_3x3_opt.gds')
    manifest['cores'][0]['def']=str(ROOT/'output/nanocgra_lite_3x3_opt/pnr/nanocgra_lite_3x3_opt.def')
    manifest['cores'][1]['gds']=str(HERE/'fulladder/gds/fulladder.gds')
    manifest['cores'][1]['def']=str(HERE/'fulladder/pnr/fulladder.def')
(ws/'assembly_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# The backend now uses native KLayout for hierarchy-aware previews.
report=padring_runner.run_padring(ws,'ChipOrchestraDualCore',{'padring':'gf180-v1','assembly_manifest':manifest})
data=report.as_dict()
(ws/'reports/padring_report.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(data['metrics'],indent=2))
