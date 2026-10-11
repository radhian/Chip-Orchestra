from pathlib import Path
import json,re
root=Path(__file__).resolve().parent
results=json.loads((root/'nanocgra_performance_20261011/performance_results.json').read_text())
assert all(results[str(c)]['passed'] and results[str(c)]['vectors']==192 for c in (8,87))
default=results['87']
p=root/'iscas2027/Chip_Orchestra_ISCAS2027.tex'
s=p.read_text()
values=[default['baud']/1000]+[default['timing'][key]['mean']/1000 for key in ('total_ns','run_read_ns','read_ns')]+[default['sequential_result_rate_per_s']]
for value in values:s=s.replace('TBD',f'{value:.2f}',1)
assert 'TBD' not in s
start=s.index('Icarus syntax')
end=s.index('\\subsection{Core Interface Tradeoff}',start)
block=s[start:end]
s=s[:start]+s[end:]
idx=s.index('\\subsection{Measured Latency and Throughput}')
s=s[:idx]+block+s[idx:]
p.write_text(s)
abstract=re.search(r'\\begin\{abstract\}\s*(.*?)\s*\\end\{abstract\}',s,re.S).group(1)
assert len(abstract)<1200
(root/'iscas2027/submission_abstract.txt').write_text(abstract+'\n')
report=['# NanoCGRA independent functional and performance validation','',
        'Run `python paper/measure_nanocgra.py` inside the documented WSL EDA environment. All work stays in the paper folder.',
        '', 'Python seed 20261011 supplies 24 operand pairs for each of eight operations. Eight boundary pairs and 16 random pairs cover each operation. Results wrap modulo 256. MAC is a single product because configuration clears its accumulator. PE00 is observed. All 32 SRAM addresses are written and read. This does not establish exhaustive mesh coverage.',
        '', 'The receiver listens concurrently with read-packet transmission. An initial sequential-receiver test missed early UART responses at divisor 87. The corrected testbench is rerun for both divisors. No RTL modification was needed.',
        '', '| Metric | Divisor 8 | Divisor 87 |','| --- | ---: | ---: |']
for label,key,scale in [('Full transaction latency (us)','total_ns',1000),('RUN to returned result (us)','run_read_ns',1000),('READ to returned byte (us)','read_ns',1000),('Core latency (cycles)','core_cycles',1)]:
 report.append(f"| {label} | {results['8']['timing'][key]['mean']/scale:.2f} | {results['87']['timing'][key]['mean']/scale:.2f} |")
report += [f"| Sequential results per second | {results['8']['sequential_result_rate_per_s']:.2f} | {results['87']['sequential_result_rate_per_s']:.2f} |",'| Passing arithmetic and SRAM checks | 224 | 224 |','',
 'Clock: 10 MHz. Core accepted start to result commit: 5 cycles, or 0.5 us. Full transaction latency starts at the first operand write and ends at completion of the returned byte. It includes six writes, RUN, 200 host-wait cycles, READ, UART framing, and sender spacing. Throughput is the reciprocal of that measured transaction time. It is not peak nine-PE compute throughput. All vectors have equal minimum, mean, and maximum latency for each setting.',
 '', f'Abstract: {len(abstract)} characters including spaces and punctuation, excluding the trailing file newline. {len(abstract.split())} words.',
 '', 'RTL simulation and fresh synthesis pass. Fresh placement and routing remain blocked by the documented OpenSTA incompatibility. The assembled retained-core GDS is readable, but approximate top-level routes have not passed full-chip electrical connectivity, DRC, or LVS. No fabricated-chip performance is claimed.']
(root/'NanoCGRA_Performance_Report.md').write_text('\n'.join(report)+'\n')
print('Default metrics',values,'abstract characters',len(abstract))
