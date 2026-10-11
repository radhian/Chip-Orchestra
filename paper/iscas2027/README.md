# Chip Orchestra ISCAS 2027 paper package

The final manuscript is `Chip_Orchestra_ISCAS2027.pdf`. The editable source is `Chip_Orchestra_ISCAS2027.tex`. All work is contained in this directory. The original DOCX remains unchanged.

## Format verification

- Official ISCAS template page permits IEEEtran in conference mode. The included IEEEtran class was extracted from the user-supplied conference template archive.
- Four technical pages and an optional fifth page containing only references. US Letter, two columns, 10 pt body, IEEEtran title and author formatting. No page numbers or security settings.
- PDF is below 5 MB. All fonts are embedded Type 1 fonts, with no Type 3 fonts.
- Body font is Nimbus Roman, a Times-compatible font used by the LaTeX Times package. It is not the literal Microsoft Times New Roman font requested. A LuaLaTeX attempt to use the installed Microsoft font failed because the runtime lacks working font-loading dependencies. This is the remaining typography deviation.
- The KLayout padframe screenshot has effective resolution of approximately 667 dpi. The NanoCGRA architecture figure is vector graphics.
- Abstract is one paragraph of 150 words and 1,062 characters including spaces and punctuation. `submission_abstract.txt` provides the text for the submission form. Five keywords are provided. Equations are numbered. Figure captions are below figures and table captions are above tables.
- Numerical citations appear in first-use order and match 11 references. Table I compares eight research studies. No semicolons appear in the rendered manuscript. LaTeX drawing commands contain required syntax delimiters.
- All four authors retain their original manuscript order and share the School of Electrical Engineering and Informatics, Bandung Institute of Technology (ITB), Bandung, Indonesia affiliation. The four email addresses supplied by the user are included in matching author order.
- Removed ACM permission text, ASP-DAC branding, sample DOI, unsupported first-of-kind claims, and the unverifiable power estimate.
- All five page renders were inspected. Raw PDF, font, image, and text checks are retained in `qa`.

## Scientific evidence

The revised paper makes NanoCGRA the primary evaluation case and organizes the content into introduction, platform and assembly method, experimental setup, results, discussion, and conclusion. Tables compare eight primary research studies, report independent functional/performance checks, and record retained-core assembly. The earlier DDPG paragraph was removed to make room for independently reproduced NanoCGRA measurements. The previous manuscript and PDF are preserved under `archive`.

Independent Python-model checks pass 192 arithmetic vectors covering all eight operations and all 32 SRAM addresses at UART divisors 8 and 87, totaling 448 checks. Clock frequency is 10 MHz. Core latency is five cycles, or 0.5 us. At the hardware default divisor 87, full host transaction latency is 2,392.10 us and sequential throughput is 418.04 results/s. These are simulated RTL measurements. They include configuration, operand transfers, fixed host wait, commands, framing, and readback. They are not peak array throughput or silicon measurements. MAC tests cover a single product after configuration clears its accumulator. PE00 is observed, so mesh routing coverage remains limited. See `../NanoCGRA_Performance_Report.md`, `../measure_nanocgra.py`, and `../nanocgra_performance_20261011`.

The repository contains NanoCGRA core reports and the GF180 padframe assembly implementation. A new NanoCGRA padframe assembly was executed on October 11, 2026 using the retained optimized core. Its actual GDSII was captured in KLayout and included as Fig. 2. Fresh NanoCGRA simulation and synthesis were also executed, but the fresh physical flow stopped before placement at an OpenSTA compatibility failure. See `../NanoCGRA_Run_Report.md` and the run workspaces for evidence. The manuscript does not claim full-chip DRC or LVS completion, fabrication readiness, or silicon measurements. These require additional evidence.

Evidence inspected at repository revision `4f20f65a4ffbfcf0e69477ba64f5fc718704c7c1` includes:

- `eda-service/toolchain/padring_runner.py`
- `eda-service/toolchain/librelane.py`
- `orchestrator-service/internal/orchestrator/dag_test.go`
- `output/nanocgra_lite/reports/flow_summary.md`
- `output/nanocgra_lite_3x3_opt/reports/flow_summary.md`
- `paper/DDPG_RL_Accelerator_ASPDAC2027_final_4p.docx`

## Build

From this directory, run `pdflatex -interaction=nonstopmode -halt-on-error Chip_Orchestra_ISCAS2027.tex` twice. A TeX installation with IEEEtran dependencies, mathptmx, TikZ, amsmath, booktabs, and graphicx is required. The included class makes the supplied template version explicit. No font paths are hardcoded.

## Submission

The PDF has not been uploaded. Ensure the submission form uses the paper's final title and lists all four authors in the same order. Update an existing submission if its title or author list differs. The author information and template pages were checked on October 11, 2026.

Official requirements: https://epapers2.org/iscas2027/ESR/authorinfo1.php

Official templates: https://epapers2.org/iscas2027/ESR/samples.php
