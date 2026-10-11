"""Preserve the extra fresh-CGRA attempt and install the retained core inputs."""
from pathlib import Path
import shutil
from build_examples import HERE,prepare,retained_cgra
ws=HERE/'cgra'
archive=ws/'attempts/fresh_openroad'
archive.mkdir(parents=True,exist_ok=True)
for directory in ('synth','pnr'):
    source=ws/directory
    if source.exists():shutil.move(str(source),str(archive/directory))
for filename in ('synth.log','pnr.log'):
    source=ws/'logs'/filename
    if source.exists():shutil.move(str(source),str(archive/filename))
source=ws/'reports/synth_stat.txt'
if source.exists():shutil.move(str(source),str(archive/source.name))
(archive/'README.md').write_text('This extra fresh hardening attempt was stopped during detailed routing. It produced no routed GDS. It is not the source of the final example core. The retained physical core provenance is recorded in ../../reports/provenance.json.\n')
prepare()
retained_cgra()
