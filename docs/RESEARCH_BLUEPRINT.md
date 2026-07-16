# Research Blueprint

## Technical title

HST ACS/WFC Two-Axis CTE Trail Audit

## Category

CCD detector physics / image analysis

## Bounded scientific question

How effectively do current ACS/WFC calibrated products suppress serial and parallel charge-transfer trails across source charge, background and transfer distance?

## Gap statement

An independent archive-product verification; not a replacement for CALACS or a new PCTETAB.

## First-release scope

The first release must be completable as a focused 4–6 hour implementation pass after data access is working. It must deliver one reproducible analysis pipeline, one deterministic example/smoke dataset, tests, 4–6 figures, a concise TeX report and a deployable research webpage.

## Validation and uncertainty

- synthetic exponential trails
- total trail-charge recovery
- bootstrap hot pixels
- FLT/FLC comparison
- header-driven geometry

## Required figures

1. detector geometry
2. example trails
3. FLT vs FLC profiles
4. suppression vs charge
5. residual vs transfer distance
6. injection recovery

## Reusable scientific modules

- `fits_io.py`
- `geometry.py`
- `hot_pixels.py`
- `trail_profiles.py`
- `stacking.py`
- `uncertainty.py`
- `provenance.py`

## Explicit exclusions

- No novelty claim beyond the bounded dataset/question/method combination.
- No causal claim from descriptive catalogue correlations.
- No hidden manual data editing.
- No unsupported precision beyond the input uncertainties.
- No production-pipeline replacement claim.
