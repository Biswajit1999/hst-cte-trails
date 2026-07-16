# Assumptions and Limitations

## Assumptions

- Archive metadata and calibration versions are recorded and interpreted correctly.
- Selection rules are deterministic and version controlled.
- Uncertainty treatment matches the measurement or numerical process.
- Synthetic examples are used only for validation and smoke testing.
- **Readout geometry convention** (`src/hst_acs_two_axis_cte_audit/geometry.py`): the CCDAMP header
  keyword identifies which corner of the assembled SCI array is adjacent to the readout amplifier,
  using the standard convention that amps C/D read out at row 0 and A/B at row NAXIS2-1 (and
  C/A at column 0, D/B at column NAXIS1-1). This is a documented, explicit convention, not
  independently re-derived from CALACS source or flight hardware drawings. If a specific
  exposure's header configuration does not match it, the sign of the inferred transfer distance
  would be flipped. The pipeline logs the inferred geometry per file so it can be sanity-checked
  against the ACS Data Handbook when real data is processed.
- **Trail model** (`trail_profiles.py`): CTE trails are modelled as a single empirical exponential,
  `I(d) = amplitude * exp(-d / length) + offset`, in the pixels between a source and the
  amplifier. This is the descriptive form used in the literature seeds (Massey et al. 2010;
  Anderson & Bedin 2010), not a multi-trap-species physical simulation of the kind CALACS/PCTETAB
  implements.
- **Trail-profile extraction excludes a `min_distance` buffer (default 4 px)** around each source
  to avoid PSF-wing contamination of the near-source pixels; this was found necessary during
  implementation (a naive distance-1 start biased both fitted amplitude and length because PSF
  wing flux falls off on the same pixel scale as a short trail).
- **Peak memory in `docs/BENCHMARK_PLAN.md` runs is measured with the stdlib `tracemalloc`**
  (Python-level allocations only), not a full process-RSS profiler such as `psutil`, which is not
  part of this project's pinned dependency set.

## Limitations

- How effectively do current ACS/WFC calibrated products suppress serial and parallel charge-transfer trails across source charge, background and transfer distance?
- The first release is intentionally bounded and does not replace mature mission or community pipelines.
- Results may apply only to the selected products, dates, detector regions, source classes or parameter range.
- Correlated errors, censoring, calibration systematics and selection effects must be discussed where relevant.
- The real-data sample (proposal 18004, F606W, a small deterministic set of exposures) is small by
  design for a first release; per-bin sample sizes for the charge/transfer-distance breakdowns may
  fall below `config/analysis.yml`'s `minimum_sample_size` and are flagged, not hidden, in
  `results/warnings.json` when that happens.
- `reports/report.tex` could not be compiled to PDF in this session (no local LaTeX toolchain);
  only the `.tex`/`.bib` source was verified for structural completeness.
