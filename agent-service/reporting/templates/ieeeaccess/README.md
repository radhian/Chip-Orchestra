# IEEE Access report template

`EXPORT` writes the final design report as `exports/final_report.tex` against the
**IEEE Access** two-column journal class and compiles it with `pdflatex` to
`exports/final_report.pdf`. Everything the compile needs lives in this folder and
is copied next to the `.tex` at export time.

| File | Origin | Notes |
|---|---|---|
| `ieeeaccess.cls` | IEEE Access author template (unmodified) | Loads `IEEEtran.cls`; defines `\history`, `\doi`, `\corresp`, `\Figure`, `\EOD`. |
| `IEEEtran.cls` | IEEE (LPPL, unmodified) | The base IEEE journal class. |
| `Logo.png`, `notaglineLogo.png`, `jtehmLogo.png` | **Chip Orchestra branding** | The class reads its running-header logo from these three slots depending on mode; all three are the Chip Orchestra mark. |
| `bullet.png` | **Chip Orchestra branding** | Section/`\EOD` bullet, in brand blue. |
| `make_logo.py` | — | Regenerates the four PNGs from the same artwork as `frontend/public/favicon.svg`. |

The document sets `\headname{Chip Orchestra}`, so the running header reads
"Chip Orchestra" with the Chip Orchestra logo rather than IEEE Access branding —
this is an internal engineering report in the IEEE Access *format*, not an IEEE
publication.

Regenerate the logos after a branding change:

```bash
python agent-service/reporting/templates/ieeeaccess/make_logo.py
```

To compile a report by hand from a task workspace:

```bash
cd <workspace>/exports && pdflatex -interaction=nonstopmode final_report.tex
```

`\graphicspath` covers `./` and `../`, so the figures resolve from either the
workspace root or `exports/`.
