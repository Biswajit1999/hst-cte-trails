# Observational FLT/FLC pair audit

This audit uses the six verified public MAST products already recorded in
`data/manifest.csv`: three ACS/WFC F606W exposures from HST proposal 18004,
each represented by an uncorrected calibrated FLT and pixel-CTE-corrected FLC
product. They are real observations, not simulations.

For each of the two detector chips in every exposure, the audit computes

\[
\delta I = I_{\rm FLC} - I_{\rm FLT}, \qquad
f_{\rm closure} = \frac{\sum_p \delta I_p}{\sum_p |I_{{\rm FLT},p}|},
\]

the robust median and median absolute deviation of `delta I`, the RMS
correction divided by the median FLT error, the median FLC/FLT error ratio, and
the fraction of pixels whose DQ bit masks disagree. Units follow the FITS
`BUNIT` keyword (`ELECTRONS`). Robust medians use a deterministic 8-pixel grid;
sums and RMS values use every finite pixel.

Before any numerical comparison, the code requires matching root name,
proposal, date, exposure time, filters and gain; FLT must record
`PCTECORR=PERFORM` and FLC must record `PCTECORR=COMPLETE`. Manifest byte counts
and SHA-256 hashes are verified by the runner.

Run with:

```bash
python scripts/audit_observational_pairs.py
```

## Interpretation boundary

This is a product-pair consistency test. Whole-chip closure can reveal large
numerical or pairing failures, but it is not a proof of photometric charge
conservation: correction can redistribute charge across chip boundaries and
the archive products include flagged pixels. Likewise, the latent untrailed
sky is unknown, so no statistic here measures absolute physical correction
accuracy. Three consecutive exposures of one field cannot characterize the
ACS/WFC population.
