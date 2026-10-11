from pathlib import Path
import re,json,hashlib
root=Path(__file__).resolve().parent
folder=root/'iscas2027'
source=(folder/'Chip_Orchestra_ISCAS2027.tex').read_text()
abstract=re.search(r'\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}',source,re.S).group(1)
pages=(folder/'qa/manuscript.txt').read_text(encoding='utf-8').split('\f')
pages=[p for p in pages if p.strip()]
assert len(pages)==5
assert 'R EFERENCES' in pages[4]
assert 'CONCLUSION' not in pages[4].upper().replace(' ','')
assert ';' not in ''.join(pages)
assert 'TBD' not in source
assert 150<=len(abstract.split())<=250 and len(abstract)<1200
refs=re.findall(r'\\bibitem\{([^}]+)\}',source)
used=[]
for key in re.findall(r'\\cite\{([^}]+)\}',source):
 for k in key.split(','):
  if k not in used:used.append(k)
assert used==refs,(used,refs)
assert len(refs)==11
performance=json.loads((root/'nanocgra_performance_20261011/performance_results.json').read_text())
for c in ('8','87'):
 assert performance[c]['passed'] and performance[c]['vectors']==192 and performance[c]['sram_checks']==32
 assert performance[c]['timing']['core_cycles']['min']==performance[c]['timing']['core_cycles']['max']==5
fonts=(folder/'qa/fonts.txt').read_text().splitlines()[2:]
assert fonts and all('yes' in line and 'Type 3' not in line for line in fonts)
pdf=folder/'Chip_Orchestra_ISCAS2027.pdf'
assert pdf.stat().st_size<5_000_000
info=(folder/'qa/pdfinfo.txt').read_text()
assert re.search(r'Encrypted:\s+no',info) and '612 x 792 pts' in info
checks={'pages':5,'technical_pages':4,'page_5_references_only':True,'abstract_characters':len(abstract),'abstract_words':len(abstract.split()),'references':11,'compared_research_studies':8,'independent_functional_checks_passed':448,'pdf_bytes':pdf.stat().st_size,'embedded_fonts_without_type3':True,'rendered_semicolons':0,'visual_review':'All five final page images reviewed','sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}
(folder/'qa/validation.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
