# Rebuild the synthetic reference report

**All outputs here are fabricated.**

## What is reproducible

`generate_synthetic_results.py` deterministically regenerates:

- all synthetic CSVs;
- synthetic metadata;
- all standalone figures.

`build_all.py` then replaces the figures inside the supplied DOCX template and converts it to PDF when LibreOffice is installed.

The report prose and table text are static in the template. This is deliberate: the generator recreates the exact current deterministic data. If you change the synthetic equations or numbers, update the DOCX prose/tables manually so that they remain consistent.

## Commands

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy pandas scipy matplotlib
python build_all.py
```

Outputs appear under `build/`. On a system without LibreOffice, the DOCX is still produced and can be exported manually.

## File mapping

The DOCX template embeds the sampler diagnostic and Figures 1a, 1b, 1c, 2, 3, and 4. Figure 5 is a standalone optional Spanish comparison.

## Integrity rule

Do not move the synthetic files into `results/`. Real report code should write to a separate empirical report directory and should include run IDs in every source table.
