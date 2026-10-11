from pathlib import Path
import re
p=Path(__file__).resolve().parent/'iscas2027/Chip_Orchestra_ISCAS2027.tex'
s=p.read_text()
def paragraph(starts,new):
 global s
 start=s.index(starts)
 end=s.find('\n\n',start)
 s=s[:start]+new+s[end:]
s=re.sub(r'\\begin\{figure\}\[t\]\n\\centering\n\\begin\{tikzpicture\}\[node distance=2.5mm.*?\\end\{figure\}\n', '',s,flags=re.S)
s=s.replace('p{2.9in}','p{2.8in}')
paragraph('The platform separates',r'The platform connects a browser interface, a Go orchestration service, Python agent and EDA services, MySQL task storage, and Redis event delivery. A directed acyclic graph represents dependencies. Each stage report retains metrics, artifact paths, warnings, errors, and raw logs. The present experiment invokes backend runners directly.')
paragraph('Repair loops consume',r'Repair uses diagnostics under a configured budget. Checks must apply to the files produced after repair. Physical metrics retain their clock, corner, and stage, since a passing simulation does not establish physical timing.')
paragraph('The backend emits binary',r'The backend exports binary GDSII, configuration, supporting DEF, a Library Exchange Format (LEF) abstract, a ring netlist, previews, and logs. Deterministic supporting files replace an unavailable external padring binary. File generation establishes neither design-rule checking (DRC) nor layout-versus-schematic (LVS) acceptance.')
paragraph('The experiment uses repository',r'The experiment copies optimized NanoCGRA RTL and testbenches at repository revision \texttt{4f20f65} into a separate workspace. The original smoke-test verdicts are adapted to the runner and waveform recording is added without changing RTL. Independent performance tests use the same copied RTL. No design is regenerated through an LLM.')
paragraph('To repeat this backend',r'To reproduce, run \texttt{paper/measure\_nanocgra.py} for independent UART checks and timestamp extraction. Run \texttt{paper/run\_nanocgra\_e2e.sh} for backend checks and hardening. Then execute \texttt{paper/assemble\_retained\_nanocgra.py} with the recorded retained core GDSII/DEF and \texttt{gf180-v1}. Preserve reports and raw logs for each attempt. The physical failure remains distinct from the retained-core assembly.')
paragraph('The fresh flow stops',r'Fresh hardening stops before placement because OpenSTA 2.5.0 lacks a clock property required by LibreLane. A local reporting-flag adaptation resolves an earlier command mismatch, but the property failure remains. Thus no fresh routed core or physical signoff is produced.')
paragraph('Fig.~\\ref{fig:padframe} is captured',r'Fig.~\ref{fig:padframe} shows the assembled GDSII with full hierarchy visible. Four signal routes connect clock, reset, receive, and transmit geometry. Three supply and four ground resources produce seven supply routes. Independent readback establishes that these shapes coexist with the ring and core.')
paragraph('The core bounding-box footprint',r'The core bounding box occupies approximately 2.53\% of the chip envelope. This is a geometric footprint ratio, not standard-cell utilization. The fixed ring dominates area, so fewer signals do not demonstrate a smaller package.')
paragraph('Assembly and signoff answer',r'Hierarchy readback establishes a readable layout containing the selected blocks. Estimated routing endpoints may miss pins or need vias and orientation transforms. Electrical continuity requires full-chip LVS against a complete core and I/O-cell netlist.')
paragraph('DRC must also be applied',r'Full-chip DRC must check new routes, supply continuity, voltage compatibility, unused-pad ties, and keep-out regions. The demonstrated assembly therefore remains short of electrically verified, fabrication-ready integration.')
paragraph('This experiment demonstrates direct',r'The experiment demonstrates backend execution, fresh RTL checks and synthesis, and retained-core assembly. It does not evaluate LLM generation, reference approval, scheduling, or autonomous repair. Engineering-effort reduction, multi-seed completion rate, and portability remain unmeasured. The hardening failure makes compatible tool versions part of the reproduction contract.')
paragraph('Future evaluation should use',r'Future work should test broader mesh configurations, UART faults, accumulated MAC sequences, and deliberate connectivity errors. A scripted baseline should measure completion rate, interventions, runtime, and cost. Compatible implementation tools, pin-accurate routing, and full-chip DRC/LVS are immediate priorities before fabrication and power measurement.')
p.write_text(s)
