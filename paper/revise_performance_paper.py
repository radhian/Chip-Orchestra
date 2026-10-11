from pathlib import Path
import re
root=Path(__file__).resolve().parent
p=root/'iscas2027/Chip_Orchestra_ISCAS2027.tex'
s=p.read_text()
abstract=('Turning generated logic into an inspectable chip requires checks across tool and interface boundaries. '
'We present Chip Orchestra, a platform that links executable reference models, hardware generation, tool reports, and padframe assembly. '
'Its backend is evaluated with NanoCGRA, a nine-element array with 32 bytes of memory and a serial interface. '
'Independent reference vectors test eight operations and every memory address at two serial settings. '
'All 448 checks pass. At 10 MHz, core result latency is five cycles. '
'Serial latency and sustained transaction rate are measured separately to expose communication overhead. '
'Fresh synthesis completes, but a timing-tool mismatch stops physical implementation before placement. '
'A separate run assembles a retained core into a 2.935 mm square ring and exports a readable layout. '
'Comparison with eight studies positions the contribution as an observable backend handoff. '
'The actual layout screenshot supports assembly evidence, while electrical connectivity and full-chip verification remain pending.')
assert len(abstract)<1200,(len(abstract),len(abstract.split()))
s=re.sub(r'(?<=\\begin\{abstract\}\n).*?(?=\n\\end\{abstract\})',lambda _:abstract,s,flags=re.S)
intro=r'''ChipGPT searches generated logic candidates~\cite{chipgpt}, and AutoChip feeds compiler and simulation diagnostics back into generation~\cite{autochip}. RTLLM separates syntax, functionality, and design quality~\cite{rtllm}, while VerilogEval compares generated behavior with golden simulation outputs~\cite{verilogeval}. Chip-Chat demonstrates engineer-guided processor design sent to a SKY130 shuttle~\cite{chipchat}. ChatEDA already coordinates RTL-to-GDSII tool execution~\cite{chateda}. OpenCGRA~\cite{opencgra} and Morpher~\cite{morpher} provide architecture and compilation ecosystems. Table~\ref{tab:related} compares these complementary scopes. Our contribution is an inspectable reference-to-assembly interface, not the first use of LLMs for chips or a demonstrated performance advantage over these systems.

\begin{table*}[t]
\caption{Comparison with Eight Hardware Generation, EDA, and CGRA Studies}
\label{tab:related}\centering\footnotesize
\begin{tabular}{p{1.0in}p{2.8in}p{2.9in}}\toprule
Study & Evaluated focus & Relation to the present experiment\\\midrule
ChipGPT~\cite{chipgpt} & Natural-language logic generation and candidate search & Generation and optimization, not our UART backend workload\\
AutoChip~\cite{autochip} & HDL repair using compiler and simulation feedback & Related repair mechanism, evaluated on HDLBits tasks\\
RTLLM~\cite{rtllm} & Syntax, functional correctness, and design quality & Broader generation benchmark than our single retained design\\
VerilogEval~\cite{verilogeval} & Golden-simulation checking on 156 HDLBits problems & Generation accuracy cannot be compared with UART throughput\\
Chip-Chat~\cite{chipchat} & Conversational eight-bit processor design and SKY130 tapeout & Stronger tapeout evidence than our geometric assembly\\
ChatEDA~\cite{chateda} & Agent task planning, script generation, and RTL-to-GDSII execution & Prior physical-flow automation, distinct evaluation workloads\\
OpenCGRA~\cite{opencgra} & Unified CGRA modeling, testing, and architecture evaluation & Architecture exploration rather than our pad-boundary handoff\\
Morpher~\cite{morpher} & CGRA compilation, simulation, synthesis, and kernel validation & Broader kernel coverage than our PE00 transaction tests\\
Chip Orchestra & Fresh UART checks and synthesis, retained-core padframe assembly & Explicit provenance, measured serial performance, signoff pending\\\bottomrule
\end{tabular}
\end{table*}
'''
needle='Chip Orchestra addresses this problem through observable task stages.'
s=s.replace(needle,intro+'\n'+needle)
start=s.index('The integration testbench writes operands')
end=s.index('\\subsection{Execution and Provenance}',start)
s=s[:start]+r'''An independent Python model generates 192 operand pairs, comprising 24 pairs for each of addition, subtraction, AND, OR, exclusive-or, multiplication, multiply--accumulate (MAC), and pass-through. Each operation uses eight boundary pairs and 16 pseudorandom pairs with seed 20261011. Results wrap to eight bits. Configuration loading clears the MAC accumulator, so the MAC cases check a single product, not accumulation across runs. A separate sweep writes and reads all 32 SRAM addresses. The output is PE00, so these tests do not establish coverage of all mesh routes.

The testbench transmits actual UART bits and checks returned bytes at a 100 ns clock period. It runs with both the accelerated eight-clock divisor and the hardware's default 87-clock divisor. Each measured result includes six three-byte writes, a run packet, a 200-cycle host wait, a read packet, and the returned byte. Latency begins at the first operand-write start bit and ends at completion of that byte. Core latency is measured separately from accepted start to result commit. The testbench asserts both arithmetic agreement and five-cycle core latency for every vector. The scripts, vectors, logs, and per-vector timestamps are retained in the paper workspace.

''' +s[end:]
start=s.index('Fresh simulation compiles and passes all four')
end=s.index('Icarus syntax',start)
s=s[:start]+r'''The original four UART smoke checks pass. The independent expanded test passes 192 arithmetic checks and 32 SRAM checks at each of two UART divisors, giving 448 passing checks. All eight operations agree with the Python model, and every tested computation commits five cycles after accepted start. This is measured RTL behavior, not exhaustive state-space verification or silicon measurement.

\subsection{Measured Latency and Throughput}
Table~\ref{tab:performance} separates core time from serial transaction time. With clock frequency $f$ and measured core cycle count $N$, core latency is $N/f=0.5\,\mu$s. Sequential throughput is
\begin{equation}
R_{\mathrm{seq}}=1/T_{\mathrm{transaction}},
\end{equation}
where $T_{\mathrm{transaction}}$ includes configuration, operands, command spacing, the fixed host wait, and returned data. It describes this reproducible host protocol, not peak array operations per second or overlapped streaming capacity.

\begin{table}[t]
\caption{Measured RTL Performance at 10 MHz}
\label{tab:performance}\centering\footnotesize
\begin{tabular}{lrr}\toprule
Metric & Divisor 8 & Divisor 87\\\midrule
UART rate (kbaud) & 1250.00 & DEFAULT_BAUD\\
Core latency (cycles) & 5 & 5\\
Core latency ($\mu$s) & 0.50 & 0.50\\
Full transaction ($\mu$s) & 239.50 & DEFAULT_TOTAL\\
RUN through returned result ($\mu$s) & 81.10 & DEFAULT_RUN\\
READ through returned byte ($\mu$s) & 34.80 & DEFAULT_READ\\
Sequential results per second & 4175.37 & DEFAULT_RATE\\
Passing arithmetic / SRAM checks & 192 / 32 & 192 / 32\\\bottomrule
\end{tabular}
\end{table}

For each divisor, minimum, mean, and maximum transaction times are identical across all 192 vectors because the host schedule and arithmetic pipeline are fixed. The default setting is the representative hardware configuration. Divisor 8 accelerates simulation and is not a measured device baud capability. Serialization dominates the five-cycle core computation. The eight-bit, start/stop-bit UART framing gives a raw byte-rate upper bound of $f/(10C)$ for divisor $C$, before command overhead and host gaps. End-to-end throughput is therefore much lower than this framing bound. Different workloads and interfaces in Table~\ref{tab:related} prevent a defensible numerical speedup comparison.

''' +s[end:]
start=s.index('An earlier actor--critic maze-accelerator')
end=s.index('Future evaluation',start)
s=s[:start]+s[end:]
s=s.replace('Fresh RTL simulation passes four UART transactions and synthesis completes','Fresh RTL simulation passes 448 checks at two serial settings, core latency is five cycles, and synthesis completes')
start=s.index('\\begin{thebibliography}')
s=s[:start]+r'''\begin{thebibliography}{11}
\bibitem{openroad} The OpenROAD Project, ``OpenROAD documentation.'' Accessed Oct. 11, 2026. [Online]. Available: \url{https://openroad.readthedocs.io/en/latest/}
\bibitem{librelane} LibreLane Contributors, ``LibreLane documentation.'' Accessed Oct. 11, 2026. [Online]. Available: \url{https://librelane.readthedocs.io/en/latest/}
\bibitem{chipgpt} K. Chang et al., ``ChipGPT: How far are we from natural language hardware design,'' 2023, arXiv:2305.14019v1.
\bibitem{autochip} S. Thakur et al., ``AutoChip: Automating HDL generation using LLM feedback,'' 2024, arXiv:2311.04887v2.
\bibitem{rtllm} Y. Lu, S. Liu, Q. Zhang, and Z. Xie, ``RTLLM: An open-source benchmark for design RTL generation with large language model,'' in \emph{Proc. ASP-DAC}, 2024, arXiv:2308.05345.
\bibitem{verilogeval} M. Liu, N. Pinckney, B. Khailany, and H. Ren, ``VerilogEval: Evaluating large language models for Verilog code generation,'' in \emph{Proc. ICCAD}, 2023, arXiv:2309.07544v2.
\bibitem{chipchat} J. Blocklove, S. Garg, R. Karri, and H. Pearce, ``Chip-Chat: Challenges and opportunities in conversational hardware design,'' in \emph{Proc. MLCAD}, 2023, doi: 10.1109/MLCAD58807.2023.10299874.
\bibitem{chateda} Z. He et al., ``ChatEDA: A large language model powered autonomous agent for EDA,'' \emph{IEEE Trans. Comput.-Aided Design Integr. Circuits Syst.}, 2024, doi: 10.1109/TCAD.2024.3383347.
\bibitem{opencgra} C. Tan, C. Xie, A. Li, K. J. Barker, and A. Tumeo, ``OpenCGRA: An open-source unified framework for modeling, testing, and evaluating CGRAs,'' in \emph{Proc. ICCD}, 2020, pp. 381--388, doi: 10.1109/ICCD50377.2020.00070.
\bibitem{morpher} D. Wijerathne, Z. Li, and T. Mitra, ``Accelerating edge AI with Morpher: An integrated design, compilation and simulation framework for CGRAs,'' in \emph{Proc. CODAI}, 2023, arXiv:2309.06127.
\bibitem{gf180} GlobalFoundries PDK Authors, ``GF180MCU PDK documentation,'' 2022. Accessed Oct. 11, 2026. [Online]. Available: \url{https://gf180mcu-pdk.readthedocs.io/en/latest/}
\end{thebibliography}
\end{document}
'''
p.write_text(s)
(root/'iscas2027/submission_abstract.txt').write_text(abstract+'\n')
print('Abstract characters',len(abstract),'words',len(abstract.split()))
