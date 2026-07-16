# Local Completion Report — HST ACS/WFC Two-Axis CTE Trail Audit

Author: Biswajit Jana. This report documents a local implementation pass.
No git operations were performed (no commit, push, remote, or repository creation), per
docs/VALIDATION_CONTRACT.md. Nothing has been published; the review checklist at the end is for
Biswajit to work through before any manual push.

## 1. Environment

- Python 3.9.19 is the system default and does **not** satisfy `pyproject.toml`'s
  `requires-python = ">=3.11,<3.13"` pin. A dedicated conda environment
  `hst-acs-cte-audit` (Python 3.11.15) was created and used for every command below.
- Node 20.14.0 / npm 10.7.0 (`D:\Softwares\nodejs`) used for the `web-react` build.
- Outbound network access to `mast.stsci.edu`, `arxiv.org`, and
  `raw.githubusercontent.com` confirmed working.
- No local LaTeX toolchain (`pdflatex`/`latexmk` not on PATH) — see §7.

## 2. Files created or changed

### Foundation
- `IMPLEMENTATION_PLAN.md` — new, Phase 1 deliverable.
- `pyproject.toml` — added `mypy` per-module overrides for untyped scientific
  dependencies (astropy/astroquery/photutils/scipy) and `types-PyYAML` dev dependency.
- `src/hst_acs_two_axis_cte_audit/config.py` — new: typed `AnalysisConfig` loader/validator.
- `src/hst_acs_two_axis_cte_audit/exceptions.py` — extended with `ArchiveAccessError`,
  `ConvergenceError`, `InsufficientDataError`.
- `src/hst_acs_two_axis_cte_audit/logging_utils.py` — new: structured logging from
  `config/logging.yml`.
- `src/hst_acs_two_axis_cte_audit/provenance.py` — extended with manifest row
  read/write, config-hash, and git-commit helpers.

### Data layer
- `scripts/fetch_data.py` — new: real MAST query + deterministic selection + download +
  checksum + manifest write, gated behind `--i-have-authorization`.
- `src/hst_acs_two_axis_cte_audit/synthetic.py` — new: the labelled-synthetic
  ACS/WFC-like data generator, shared by the test suite and `--demo` scripts (moved out
  of `tests/conftest.py` to avoid duplicating the injection model).
- `scripts/sync_web_assets.py` — new: copies `results/`, `figures/`, and
  `data/manifest.csv` into `web-react/public/`.

### Scientific modules (`src/hst_acs_two_axis_cte_audit/`)
- `fits_io.py`, `geometry.py`, `hot_pixels.py`, `trail_profiles.py`, `stacking.py`,
  `uncertainty.py` — implemented from the `NotImplementedError` stubs.
- `core.py` — added `pair_flt_flc` and `run_pipeline` orchestration on top of the
  existing starter functions.
- `results_io.py` — new: `results/summary.json` writer/validator matching
  `results/summary.schema.json`.

### Tests (`tests/`)
- `conftest.py` (fixture layer), `test_data_layer.py`, `test_geometry.py`,
  `test_fits_io.py`, `test_trail_profiles.py`, `test_uncertainty.py`,
  `test_hot_pixels.py`, `test_stacking.py`, `test_core_pipeline.py`,
  `test_results_io.py` — all new. `test_starter_core.py` unchanged.

### Figures and report
- `scripts/make_figures.py` — implemented all 6 required figures (demo + real-data paths).
- `reports/report.tex`, `reports/references.bib` — completed with verified citations
  and real-data results.
- `docs/ASSUMPTIONS_AND_LIMITATIONS.md` — extended with the explicit geometry/trail-model
  assumptions made during implementation.

### Web dashboard (`web-react/`)
- `src/App.jsx` — rewritten: reads `results/summary.json`, `results/warnings.json`,
  `project.json` at runtime; renders metrics with uncertainty, figure gallery,
  provenance, validation contract, warnings, methodology, assumptions/limitations,
  downloads, citation. No hard-coded research values, no fake live-data language.
- `public/project.json` — trimmed to genuinely static metadata; removed the placeholder
  demo metrics/chart.
- `eslint.config.js` — **bug fix**: added `react/jsx-uses-vars` (missing from the
  scaffold), without which ESLint's `no-unused-vars` doesn't recognise `<Component />`
  JSX usage and false-flags every custom component as unused.
- `package.json` — removed the unused `recharts` dependency (no longer imported after
  the placeholder chart was replaced with the real figure gallery).

### Real data (git-ignored, not committed)
- `data/manifest.csv` — 6 rows, one per real downloaded FITS file.
- `data/raw/*.fits` — 6 real ACS/WFC files (~964 MB total).
- `results/summary.json`, `results/warnings.json`, `results/benchmarks.json` — generated,
  real-data values.
- `figures/fig01–fig06.{svg,png,json}` — generated from real data.

## 3. Exact commands run (in order)

```bash
conda create -n hst-acs-cte-audit python=3.11 -y
python -m pip install -e ".[dev]"
python -m pip install types-PyYAML
pytest -q                                  # 57 passed
ruff check src tests scripts               # All checks passed
mypy src                                   # Success: no issues found in 15 source files
python scripts/run_analysis.py --demo
python scripts/make_figures.py --demo
cd web-react && npm install && npm run build && npm run lint
python scripts/sync_web_assets.py
# Real-data pipeline, run only after explicit operator authorization in chat:
python scripts/fetch_data.py --i-have-authorization --n-exposures 3
python scripts/run_analysis.py
python scripts/make_figures.py
python scripts/sync_web_assets.py
cd web-react && npm run build              # re-verified after real data synced
```

## 4. Test / lint / build results

- **pytest**: 57 tests passed, 0 failed (verified both by exit code and by direct
  `grep -c "^def test_"` across `tests/*.py`). Coverage: 90% overall
  (`pytest --cov=src`); `plotting.py` is 0% covered by pytest because it is only
  exercised by `scripts/make_figures.py --demo`, run separately.
- **ruff**: clean on `src tests scripts`.
- **mypy**: clean on `src` (0 errors, 15 source files).
- **web-react**: `npm run build` succeeds (155.98 kB JS, gzip 49.65 kB); `npm run lint`
  clean after the `eslint.config.js` fix.
- `npm audit`: 5 advisories, all in dev tooling (`eslint`/`@eslint/plugin-kit` config
  parser ReDoS, `esbuild` dev-server request forgery, `postcss` stringify XSS) — none
  exploitable in this local, non-deployed build; fixing them requires bumping pinned
  versions outside the range specified in the original `package.json`, which was not
  done without being asked.

### Bugs found and fixed during implementation
1. `core._measure_pair` only caught `InsufficientDataError`, not `ConvergenceError`,
   so a single non-converging per-source fit crashed the entire real-data pipeline
   run. Fixed to skip-and-warn, consistent with `docs/ERROR_HANDLING.md`.
2. `trail_profiles.compare_flt_flc_suppression` had no sanity bound: a fit can pass
   the covariance-conditioning gate yet still return a wildly unphysical
   amplitude/length, producing suppression fractions like 22.9 that dominated bin
   means. Added `SUPPRESSION_FRACTION_SANITY_BOUND = 3.0`, raising `ConvergenceError`
   (recorded as a warning, not silently dropped) outside that range.
3. `scripts/make_figures.py`'s real-data path used only the single brightest detected
   source for the example-trail and FLT-vs-FLC-profile figures, with no fallback; that
   source's fit did not converge. Fixed to try up to 15 bright candidates and use the
   first one that fits successfully in both FLT and FLC.
4. `scripts/fetch_data.py` downloaded files into astroquery's nested
   `mastDownload/HST/<obs_id>/` layout, but `core.pair_flt_flc` expected a flat
   `data/raw/<product_id>.fits` layout — real downloads would never have paired
   correctly. Fixed to flatten on download and to skip the association-level combined
   FLC products (no FLT counterpart, would only waste bandwidth).
5. `web-react/eslint.config.js` was missing `react/jsx-uses-vars`, causing ESLint to
   false-flag every custom JSX component as unused (see §2).
6. `scripts/run_analysis.py --demo` wrote a `results/summary.json` that did not
   conform to `results/summary.schema.json` (missing `metrics`/`provenance`/`warnings`
   keys) — would have broken the web dashboard's fetch. Fixed to use the same
   `results_io.write_summary` path as the real-data run.

## 5. Real datasets accessed

Queried live against MAST (`astroquery.mast.Observations`), no fabricated metadata.

- **Program**: HST proposal 18004, PI Matthew Hayes, ACS/WFC, filter F606W, calibration
  level 2 (FLT/FLC), field near RA 53.27, Dec −27.79 (GOODS-South region).
- **Selection**: deterministic first-3 exposures by sorted `obs_id`, confirmed
  `dataRights=PUBLIC` for each before download.
- **Files** (6 total, `data/manifest.csv`, SHA-256 verified against the downloaded
  bytes with `sha256sum`):

| product_id | sha256 | bytes |
|---|---|---|
| jfnx01mhq_flt | `a78170d39b5b51dbb9a5241367e50f6978734958101e4a66be613871272121cc` | 168431040 |
| jfnx01mhq_flc | `424766cca22444571dbe8bd430c1e0ae7eab081d1c71cc61d183b6cecae05741` | 168439680 |
| jfnx01miq_flt | `464666d8012f47b49ddb92ebefd146bb92ec96be06c7a61bb0a764373268515d` | 168431040 |
| jfnx01miq_flc | `8a2f885f193d509b7f67102513a21be9949afcdb44dd2374e7ce8daf3be5baa8` | 168439680 |
| jfnx01mkq_flt | `da17071401941a077099229fad2d61953b18914ab8f96cb8a8526efcf770d885` | 168431040 |
| jfnx01mkq_flc | `5cbeef2a75947b8b25aabdcd355fe07b571be82f6473741875d805a875ca9b5f` | 168439680 |

- **Licence/terms**: STScI/MAST public HST archive data, no proprietary period;
  standard STScI archive usage terms apply.
- Raw FITS files are **not committed** (`.gitignore` already excluded `data/raw/*`).

## 6. Validation and uncertainty outcomes

- **Synthetic injection-recovery gate** (`tests/test_trail_profiles.py`): PASSED.
  Across 15 independent noise realizations at signal level (flux 20,000 e⁻, trail
  amplitude fraction 0.05, length 6 px), worst-case amplitude recovery error was 6.8%,
  worst-case length recovery error was 10.6%; the automated test enforces 15%/25%
  tolerances with margin. This is the pass/fail gate docs/VALIDATION_CONTRACT.md requires before
  trusting the pipeline on real data.
- **Null control**: a flat, no-trail synthetic profile fits an amplitude consistent
  with zero.
- **Failure-mode tests**: non-finite input, too-few-points, mismatched array shapes,
  missing FITS extensions, missing header keywords, and unphysical suppression values
  all raise the documented exceptions rather than silently producing a result.
- **Real-data result**: 120 candidate sources detected across 3 FLT/FLC pairs; 84
  rejected by fit-quality or physical-plausibility checks (recorded in
  `results/warnings.json`, not dropped silently); n=36 usable measurements. Median
  trail-charge suppression fraction: **0.79**. Charge- and transfer-distance-binned
  means are reported but every bin (n≈12–13) is below `config/analysis.yml`'s
  `minimum_sample_size=30` and is flagged as underpowered in `results/warnings.json`.
- **Hot pixels**: DQ bit 16 (ACS `HOTPIX`) verified directly against the real CALACS
  source (`spacetelescope/hstcal`, `pkg/acs/include/acsdq.h`) rather than assumed.
  Bootstrap mean excess −5.5 e⁻ (95% CI [−7.8, −3.4], n=497,229 pixels); the negative
  sign is plausible given dark-current subtraction in the calibrated FLT product but
  was not independently confirmed against a raw (non-dark-subtracted) product.
- **Numerical vs. observational uncertainty**: kept separate throughout — bootstrap
  resampling (1000 resamples, seed 20260713, 95% CI) for observational uncertainty;
  fit covariance condition number and reduced χ² for numerical convergence, per
  `hst_acs_two_axis_cte_audit.uncertainty`.

## 7. Remaining TODOs / unresolved risks

- `reports/report.tex` could not be compiled to PDF locally (no `pdflatex`/`latexmk`
  on this machine). Structural balance (braces, `\begin`/`\end` pairs) was checked
  programmatically and is correct, but the PDF itself has not been visually verified.
  **Action for Biswajit**: compile with a local or Overleaf LaTeX install before
  treating the PDF as final.
- `reports/references.bib`: the two literature seeds (Anderson & Bedin 2010; Massey
  et al. 2010) were verified against their arXiv abstract pages this session. The ACS
  Data Handbook / CALACS documentation entries are marked `TODO_VERIFY` for a specific
  edition/version pin — they were not fabricated, just not pinned to a dated version.
- The real-data sample is intentionally small (3 exposures, 1 program, 1 filter,
  1 epoch) — a first-release bounded check, not a general characterization of ACS/WFC
  CTE performance.
- `npm audit` flags 5 dev-tooling-only advisories (see §4); not fixed, since doing so
  requires bumping pinned versions outside `package.json`'s stated range without
  being asked to.
- Hot-pixel excess sign (§6) is plausible but not independently cross-checked against
  a raw (non-dark-subtracted) product in this session.

## 8. Claims safe for a public README

- "Implements a reproducible pipeline auditing ACS/WFC FLT-vs-FLC CTE trail
  suppression, validated against a synthetic injection-recovery gate before use on
  real data."
- "On a small, deterministic sample of 3 public ACS/WFC F606W exposure pairs (HST
  proposal 18004), median trail-charge suppression fraction was 0.79 (n=36 sources)."
- "57 automated tests, including null controls and failure-mode tests, at 90% source
  coverage; ruff- and mypy-clean."
- "An independent archive-product verification; not a replacement for CALACS or a new
  PCTETAB."

## 9. Claims that must NOT be made

- Do not claim this characterizes ACS/WFC CTE performance in general — the sample is
  3 exposures from one program/filter/epoch.
- Do not claim the charge- or transfer-distance-binned trends are statistically
  significant — every bin is below the configured minimum sample size.
- Do not claim the TeX report PDF has been visually verified — only its source
  structure was checked.
- Do not claim the hot-pixel excess sign/magnitude has been physically validated
  beyond the plausibility argument in §6.
- Do not claim this replaces or supersedes CALACS/PCTETAB.

## 10. Manual review checklist for Biswajit

- [ ] Compile `reports/report.tex` locally/Overleaf and read the PDF end-to-end.
- [ ] Spot-check 2–3 of the `results/warnings.json` skip reasons against the actual
      FITS cutouts to confirm the skip logic is sound, not overly aggressive.
- [ ] Decide whether to pin `TODO_VERIFY` entries in `reports/references.bib` to a
      specific ACS Data Handbook/CALACS documentation edition before public release.
- [ ] Review `docs/ASSUMPTIONS_AND_LIMITATIONS.md`'s readout-geometry convention
      against the ACS Data Handbook if a stronger correctness guarantee is wanted than
      "documented, explicit assumption, self-consistent under test."
- [ ] Decide whether 3 exposures is a sufficient real-data sample for a first public
      release, or whether to fetch more before publishing (re-run
      `scripts/fetch_data.py --n-exposures N` with a larger N; each additional
      exposure pair is ~320 MB).
- [ ] Review `npm audit` output and decide whether to bump pinned frontend tooling
      versions.
- [ ] Follow `MANUAL_GITHUB_ONE_BY_ONE.md` for the actual repository creation and push
      — none of that was done in this session.
