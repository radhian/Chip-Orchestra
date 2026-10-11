# NanoCGRA independent functional and performance validation

Run `python paper/measure_nanocgra.py` inside the documented WSL EDA environment. All work stays in the paper folder.

Python seed 20261011 supplies 24 operand pairs for each of eight operations. Eight boundary pairs and 16 random pairs cover each operation. Results wrap modulo 256. MAC is a single product because configuration clears its accumulator. PE00 is observed. All 32 SRAM addresses are written and read. This does not establish exhaustive mesh coverage.

The receiver listens concurrently with read-packet transmission. An initial sequential-receiver test missed early UART responses at divisor 87. The corrected testbench is rerun for both divisors. No RTL modification was needed.

| Metric | Divisor 8 | Divisor 87 |
| --- | ---: | ---: |
| Full transaction latency (us) | 239.50 | 2392.10 |
| RUN to returned result (us) | 81.10 | 669.50 |
| READ to returned byte (us) | 34.80 | 362.50 |
| Core latency (cycles) | 5.00 | 5.00 |
| Sequential results per second | 4175.37 | 418.04 |
| Passing arithmetic and SRAM checks | 224 | 224 |

Clock: 10 MHz. Core accepted start to result commit: 5 cycles, or 0.5 us. Full transaction latency starts at the first operand write and ends at completion of the returned byte. It includes six writes, RUN, 200 host-wait cycles, READ, UART framing, and sender spacing. Throughput is the reciprocal of that measured transaction time. It is not peak nine-PE compute throughput. All vectors have equal minimum, mean, and maximum latency for each setting.

Abstract: 1062 characters including spaces and punctuation, excluding the trailing file newline. 150 words.

RTL simulation and fresh synthesis pass. Fresh placement and routing remain blocked by the documented OpenSTA incompatibility. The assembled retained-core GDS is readable, but approximate top-level routes have not passed full-chip electrical connectivity, DRC, or LVS. No fabricated-chip performance is claimed.
