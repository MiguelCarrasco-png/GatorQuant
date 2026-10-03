# LaTeX sources (Overleaf-ready)

One Overleaf project, two root documents, so both PDFs share one preamble and one `generated/` folder and every number agrees.

- `paper.tex`: design paper (≤ 12 pp). Sections in `paper/`.
- `appendix.tex`: evidence appendix (≤ 12 pp). Sections in `appendix/`.
- `preamble.tex`: 10 pt, 1 in margins (the brief's minimums; don't go lower), `\gen{}`, `\pending{}`, `\implemented`/`\extension` labels.
- `generated/`: tables (`*.tex`) and number macros (`*_macros.tex`) written by `code/*.py`. Never edit by hand; rerun the script.

## Build locally

MiKTeX is installed on Miguel's machine (missing packages auto-install). From `latex/`, run each twice:

```bash
pdflatex -interaction=nonstopmode appendix.tex
```

```bash
pdflatex -interaction=nonstopmode paper.tex
```

PDFs are git-ignored; rebuild them rather than committing them.

## Upload to Overleaf

1. Zip this `latex/` folder (contents at the zip root) → Overleaf → New Project → Upload Project.
2. Menu → Main document: pick `paper.tex` or `appendix.tex` and recompile. Download each PDF.
3. After rerunning any script, re-upload the changed files in `generated/`.

## Before submitting

- Search each PDF for `PENDING` and `missing generated`: none may remain.
- Check page counts: paper ≤ 12 including references, appendix ≤ 12.
- Work through the checklist comments at the top of `paper.tex` and `appendix.tex`.

Each section file starts with its page budget from the brief (s.8). Paper: 5 + 2 + 2 + 2 + 1. Appendix: E1 1.5, S1/E2/E3 5, S2 2, S3 1, E4 1.5, E5 1.
