# Implementation Plan — HST ACS/WFC Two-Axis CTE Trail Audit

Status: Phase 1 (audit) complete. This document is updated, not replaced, as later phases reveal new constraints.

## 1. Environment audit

- System default `python` is 3.9.19; `pyproject.toml` pins `requires-python = ">=3.11,<3.13"` and exact versions of numpy/scipy/astropy/astroquery/photutils.
  **Resolution:** created a dedicated conda env `hst-acs-cte-audit` (Python 3.11.15) and installed the package with `pip install -e ".[dev]"` there. All later commands in this plan and in `LOCAL_COMPLETION_REPORT.md` run through that interpreter
  (`C:\Users\biswa\anaconda3\envs\hst-acs-cte-audit\python.exe`), not the system `python`.
- Node 20.14.0 / npm 10.7.0 available (`D:\Softwares\nodejs`) — sufficient for the `web-react` Vite build.
- No local LaTeX toolchain (`pdflatex`/`latexmk` not on PATH). **Risk accepted:** `reports/report.tex` will be completed as valid, compilable LaTeX source and checked for obvious syntax issues, but PDF compilation cannot be verified locally in this session. Documented as a limitation, not silently skipped.
- Outbound network access to `mast.stsci.edu` and `arxiv.org` confirmed working from this environment.

## 2. Dataset decision (real data, verified against MAST)

Queried `astroquery.mast.Observations` live (no fabrication):

- Instrument: ACS/WFC, `dataproduct_type=image`, `calib_level=2` (calibrated FLT/FLC).
- Selected program: **HST proposal 18004** (PI: Matthew Hayes), filter F606W, field near RA 53.272, Dec −27.790 (GOODS-South region). Confirmed `dataRights = PUBLIC` on the observation record — no proprietary embargo.
- Both `_flt.fits` (CTE-uncorrected) and `_flc.fits` (pixel-based CTE-corrected, Anderson & Bedin algorithm) products exist per exposure — this is the FLT-vs-FLC pair the audit needs.
- Two distinct exposure times observed in this program (462 s and 477 s) give a modest source/background charge contrast within one deterministic, small sample.
- Each full-frame FLT or FLC is ~168 MB uncompressed. **Sample budget:** download 3 FLT+FLC exposure pairs deterministically (first 3 by sorted `obs_id` after the PUBLIC/F606W/calib_level filter) ≈ 1 GB total, kept under `data/raw/` (git-ignored, never committed). This is enough to cover the full parallel-transfer-distance range (each frame spans all 2048 rows per quadrant) and a small source/background charge contrast, matching the "first release, 4–6 hour pass" scope in `docs/RESEARCH_BLUEPRINT.md`.
- `scripts/fetch_data.py` will implement this query + deterministic sort + download + SHA-256 + `data/manifest.csv` row per file, recording `product_id, source, source_url, retrieved_utc, sha256, file_size_bytes, selection_reason, licence_or_terms`.
- Data-use terms: MAST/STScI public HST data, no redistribution restriction for derived, non-bulk scientific use; `licence_or_terms` field will record "STScI/MAST public HST archive data, no proprietary period" verbatim per file.

## 3. Literature verification (done in Phase 1)

Both seeds in `docs/LITERATURE_SEEDS.md` checked against arXiv abstracts directly:

- Anderson & Bedin 2010, "An Empirical Pixel-Based Correction for Imperfect CTE. I. HST's Advanced Camera for Surveys", PASP, arXiv:1007.3987 — **verified**.
- Massey et al. 2010, "Pixel-based correction for Charge Transfer Inefficiency in the Hubble Space Telescope Advanced Camera for Surveys", MNRAS 401:371–384, arXiv:0909.0507 — **verified**.
- STScI ACS Data Handbook / CALACS documentation: will cite as institutional documentation (URL only, no invented DOI); marked `TODO_VERIFY` in `references.bib` only if a specific edition/version cannot be pinned down.

## 4. Scientific method (bounded to the stated question)

Serial and parallel CTE trails: radiation-damaged Si traps release charge with a delay during CCD readout, producing an exponentially-decaying trail behind each source/hot pixel along the serial (x) and parallel (y, clocked-to-readout) directions. FLC products have the Anderson & Bedin pixel-based correction applied; FLT products do not. The audit measures trail amplitude/shape in both product types for the same exposures and quantifies:

1. **Trail profile model:** exponential decay `I(d) = A * exp(-d / L) + c`, fit independently per axis, per source, per product type.
2. **Suppression metric:** ratio (or fractional reduction) of total trailed charge FLC vs FLT, as a function of (a) source charge (flux), (b) local background level, (c) parallel transfer distance (row index from readout).
3. **Hot pixels** (from the DQ mask / warm-pixel population) as a second, independent trail-injecting population, cross-checked against source-star trails with bootstrap uncertainty.
4. **Synthetic injection-recovery gate:** before touching real data, inject known synthetic exponential trails into a blank/low-background cutout and confirm the fitting code recovers the injected amplitude/length within a documented tolerance — this is the pass/fail gate required by `docs/VALIDATION_CONTRACT.md` and `docs/VALIDATION_CONTRACT.md` ("stop conditions" — if synthetic recovery fails, stop and document, do not proceed to interpret real data as if it worked).

## 5. File-level task list

### Phase 2 — Foundation
- `src/hst_acs_two_axis_cte_audit/config.py` (new): typed `dataclass`/`TypedDict` config loader + validator for `config/analysis.yml`, raising `DataSchemaError` on missing/invalid keys.
- `src/hst_acs_two_axis_cte_audit/exceptions.py`: extend with `ArchiveAccessError`, `ConvergenceError`, `InsufficientDataError` (used by later modules per `docs/ERROR_HANDLING.md`).
- `src/hst_acs_two_axis_cte_audit/logging_utils.py` (new): structured logger built from `config/logging.yml`.
- `src/hst_acs_two_axis_cte_audit/provenance.py`: extend beyond `sha256_file` with a manifest-row writer/reader and a config-hash function (git commit + config sha256), used by `results/summary.json`.
- Seed policy: single `RANDOM_SEED = 20260713` (matches `config/analysis.yml`) threaded through every stochastic step (bootstrap, synthetic injection).

### Phase 3 — Data layer
- `scripts/fetch_data.py`: real `astroquery.mast` query as described above, deterministic selection, download to `data/raw/`, checksum, append rows to `data/manifest.csv`, update `data/provenance.yml`. Guarded so it is never invoked automatically by tests.
- `tests/` fixtures: tiny synthetic FITS-like arrays (NOT the real 168 MB files) built in-memory or as small `.npz`/`.fits` fixtures under `tests/fixtures/` for fast, deterministic unit tests.
- `data/INPUT_SCHEMA.md` mapping: FLT/FLC logical fields → real FITS extensions (`SCI`, `ERR`, `DQ` for ACS/WFC; header keywords `EXPTIME`, `CCDGAIN`, `SUBARRAY`, WCS keywords) documented in `fits_io.py` docstrings.

### Phase 4 — Scientific modules (all under `src/hst_acs_two_axis_cte_audit/`)
- `fits_io.py`: load ACS/WFC FLT/FLC (SCI+ERR+DQ per chip extension), validate against `INPUT_SCHEMA.md`, raise `DataSchemaError` on missing extensions.
- `geometry.py`: header-driven detector geometry — amplifier quadrant layout, serial/parallel readout direction, pixel-to-transfer-distance mapping from `CCDCHIP`/`LTV`/`BIASSEC`/`WCS` keywords (no hard-coded geometry).
- `hot_pixels.py`: DQ-mask-driven + sigma-clipped hot/warm pixel detection, independent of source detection.
- `trail_profiles.py`: `photutils`-based source detection, per-source 1-D trail extraction along serial and parallel axes, exponential model fit (`scipy.optimize.curve_fit`) with fit-quality diagnostics.
- `stacking.py`: charge-binned and transfer-distance-binned stacking/averaging of trail profiles for a per-bin S/N boost, explicit bin edges recorded in output.
- `uncertainty.py`: bootstrap resampling (per `config/analysis.yml`: 1000 resamples, 95% CI) for all reported metrics; separate numerical (fit-convergence) uncertainty from measurement (photon/read-noise, bootstrap) uncertainty per this project's non-negotiable restrictions rule 6.
- `core.py`: keep existing starter functions (used by smoke tests); add a thin `run_pipeline()` orchestrator that composes the modules above — this is what `scripts/run_analysis.py` calls for the non-demo path.

### Phase 5 — Validation and QA
- `tests/test_trail_profiles.py`: synthetic exponential trail injection + recovery (amplitude/length within documented tolerance) — the required pass/fail gate.
- `tests/test_uncertainty.py`: bootstrap CI coverage sanity check on a known synthetic distribution.
- `tests/test_hot_pixels.py`: bootstrap hot-pixel population recovery on synthetic DQ-flagged data.
- `tests/test_geometry.py`: header-driven geometry parsing, including a **failure test** for malformed/missing header keywords.
- `tests/test_negative_controls.py`: (a) null control — no injected trail ⇒ fitted amplitude consistent with zero within uncertainty; (b) expected-failure — pathological input (empty array, non-finite values, mismatched array shapes) raises the documented exception rather than silently producing a result.
- `docs/BENCHMARK_PLAN.md` execution: record wall time, peak memory, CPU/OS, Python version, dataset size for both `--demo` and real-data runs into `results/benchmarks.json`.

### Phase 6 — Figures and report
- `scripts/make_figures.py`: implement the 6 required figures (detector geometry, example trails, FLT-vs-FLC profiles, suppression vs charge, residual vs transfer distance, injection recovery), each saved as SVG + 300 dpi PNG with a sidecar JSON (git commit, config hash, sample size, units).
- `reports/report.tex` / `reports/references.bib`: fill in Data/Method/Validation/Results/Reproducibility sections from real `results/summary.json`; keep `TODO_VERIFY` only where a claim truly cannot be independently checked in this session (expected: none, since both seed citations are already verified).

### Phase 7 — React dashboard
- `web-react/public/project.json`: keep static project metadata (title/question/status) but stop hard-coding metrics/chart placeholders.
- `web-react/src/App.jsx`: fetch `results/summary.json` (copied into `web-react/public/results/`) in addition to `project.json`; render real metrics with uncertainty, a provenance/download panel (manifest rows, checksums), methodology/validation/limitations tabs, and the figure gallery (served from `figures/`). Preserve the existing restrained dark dashboard styling; no fake "live" language.

### Phase 8 — Verification
- Run the full command sequence from the project root instructions using the `hst-acs-cte-audit` conda interpreter, repair failures, then write `LOCAL_COMPLETION_REPORT.md`.

## 6. Validation thresholds (from `docs/VALIDATION_CONTRACT.md`, made concrete)

| Check | Threshold |
|---|---|
| Synthetic trail amplitude recovery | recovered within 10% of injected amplitude, bootstrap 95% CI covers truth |
| Synthetic trail length recovery | recovered within 15% of injected decay length |
| Minimum sample size per bin | ≥30 (per `config/analysis.yml`) — bins below this are flagged in `results/warnings.json`, not silently dropped |
| Bootstrap resamples | 1000, seed 20260713 |
| Finite-value check | 100% of reported metric arrays finite after documented masking |
| Null control | zero-injection trail amplitude consistent with 0 at 95% CI |

## 7. Unresolved risks / stop-condition watchlist

- **LaTeX compilation cannot be verified locally** (no `pdflatex`) — documented as a limitation in `LOCAL_COMPLETION_REPORT.md`, not silently ignored.
- **Real FLT/FLC download is ~1 GB and network-dependent** — if the download fails or is truncated mid-session, the pipeline must fail loudly (`ArchiveAccessError`), not fall back to fabricated values; the `--demo` synthetic path remains the fallback smoke path only, and is never presented as a scientific result.
- **photutils 1.13.0 API surface** will be checked against the installed version at implementation time (not assumed from memory) before writing `trail_profiles.py`.
- If synthetic injection-recovery fails to meet the thresholds above, per this project's non-negotiable restrictions stop conditions: stop, document in `results/warnings.json` and `LOCAL_COMPLETION_REPORT.md`, and do not proceed to interpret the real FLT/FLC data as if validated.
- STScI ACS Data Handbook / CALACS documentation citations will use stable STScI documentation URLs rather than invented DOIs; if no stable citation form is found, mark `TODO_VERIFY`.

## 8. Non-negotiables carried forward

No `git commit`/`push`/remote creation at any phase. Biswajit Jana remains sole author in `CITATION.cff`. No fabricated data, benchmarks, or citation metadata.
