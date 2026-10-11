from pathlib import Path
import hashlib,json,re
import gdstk
HERE=Path(__file__).resolve().parent
ws=HERE/'combined_padframe'
gds=ws/'padring/ChipOrchestraDualCore_chip.gds'
connectivity=json.loads((ws/'reports/gds_connectivity.json').read_text())
assert connectivity['independent_signal_connections_verified']==9
assert connectivity['independent_power_connections_verified']==4
assert connectivity['signal_shorts']==connectivity['orphan_vias']==0
assembly=json.loads((ws/'padring/pin_assembly_report.json').read_text())
assert assembly['core_count']==2 and assembly['routes_signal']==9 and assembly['routes_power']==4
assert assembly['actual_pad_summary']['total_io']==73
assert assembly['actual_pad_summary']['corners']==4
assert assembly['minimum_route_widths_um']['Metal5']==0.44
lib=gdstk.read_gds(str(gds))
top=next(c for c in lib.cells if c.name=='ChipOrchestraDualCore_chip')
names=[r.cell.name for r in top.references]
assert set(names)=={'RING_PAD','u_cgra__NanoCGRA_Lite','u_fulladder__fulladder'}
fa=(HERE/'fulladder/logs/gls_simulation.log').read_text()
cgra=(HERE/'cgra/logs/performance_tb_simulation.log').read_text()
pad=(ws/'logs/pad_function_simulation.log').read_text()
assert 'TEST PASSED fulladder checks=8' in fa
assert 'TEST PASSED checks=224 vectors=192 CPB=87' in cgra
assert 'TEST PASSED fulladder through GF180 pads checks=8' in pad
assert 'TEST PASSED checks=224 vectors=192 CPB=87' in pad
assert 'FAIL' not in fa+cgra+pad
assert '7 passed' in (HERE/'backend_tests.log').read_text()
for file in [HERE/'fulladder/gds/fulladder.png',HERE/'cgra/gds/NanoCGRA_Lite.png',ws/'padring/ChipOrchestraDualCore_chip_preview.png',ws/'padring/two_core_detail.png']:
 assert file.is_file() and file.stat().st_size>1000
provenance=json.loads((HERE/'cgra/reports/provenance.json').read_text())
assert provenance['gds_sha256']==hashlib.sha256((HERE/'cgra/gds/NanoCGRA_Lite.gds').read_bytes()).hexdigest()
summary={'generated_combined_padframe':True,'physical_core_instances':names,'fulladder_post_route_checks':8,'cgra_default_uart_checks':224,
         'official_gf180_pad_model_checks':232,'backend_regression_tests_passed':7,
         'signal_connections_verified':9,'power_connections_verified':4,'top_level_vias_verified':connectivity['top_level_vias_checked'],
         'signal_shorts':0,'orphan_vias':0,'cgra_physical_source':provenance['physical_core'],
         'fulladder_physical_source':'Fresh Yosys/OpenROAD/KLayout implementation',
         'full_chip_foundry_drc_or_device_lvs_claimed':False,
         'gds_bytes':gds.stat().st_size,'gds_sha256':hashlib.sha256(gds.read_bytes()).hexdigest()}
(HERE/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
