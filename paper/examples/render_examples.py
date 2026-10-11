from pathlib import Path
import os,sys,subprocess
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'eda-service'))
from toolchain.padring_runner import _render_gds_preview
for name,top in [('fulladder','fulladder'),('cgra','NanoCGRA_Lite')]:
 ws=HERE/name
 assert _render_gds_preview(ws/f'gds/{top}.gds',ws/f'gds/{top}.png',top)
script=HERE/'combined_padframe/padring/render_core_detail.py'
script.write_text('''import pya,os
window=pya.Application.instance().main_window()
window.load_layout(os.environ['CHIP_GDS'],0)
view=window.current_view()
view.add_missing_layers()
view.max_hier()
view.zoom_box(pya.DBox(1080,1140,2070,1840))
view.set_config('background-color','#ffffff')
view.set_config('grid-visible','false')
view.set_config('text-visible','false')
view.save_image(os.environ['CHIP_IMAGE'],2200,1600)
pya.Application.instance().exit(0)
''')
env=os.environ.copy()
env['QT_QPA_PLATFORM']='offscreen'
env['CHIP_GDS']=str(HERE/'combined_padframe/padring/ChipOrchestraDualCore_chip.gds')
env['CHIP_IMAGE']=str(HERE/'combined_padframe/padring/two_core_detail.png')
subprocess.run(['klayout','-z','-r',str(script)],env=env,check=True,timeout=90)
print('Native GDS screenshots generated')
