# Synthetic trail-inference validation

This validation layer asks whether the repository's empirical exponential
trail model can recover known inputs under controlled conditions. It uses no
HST exposure and does not revise the published CALACS 10.4.1 audit.

## Weighted estimator and uncertainty

For distance `d` in pixels, the fitted profile is

`I(d) = A exp(-d / tau) + B`,

with `A` and `B` in electrons and `tau` in pixels. Fits use supplied absolute
one-sigma errors, so the covariance matrix is on the input electron scale.
The 600-trial coverage experiment checks how often nominal 95% Wald intervals
contain injected `A` and `tau`, and separately records numerical failures and
reduced chi-square.

## Fitting-window sensitivity

A short 1.2-pixel PSF-wing component is added to a 6-pixel synthetic trail.
The first fitted pixel is swept from 2 to 6 and the final pixel from 12 to 22.
This quantifies the bias controlled by the existing four-pixel source buffer;
it does not prove that four pixels is optimal for every ACS source or filter.

## Model misspecification

Profiles containing fast (`tau=3 px`) and slow (`tau=12 px`) components are
fit with the single-exponential model. The diagnostic reports bias in
integrated trail charge, `Q = A tau`, and reduced chi-square as the slow/fast
amplitude ratio increases. The components are an identifiability stress test,
not an estimate of physical HST trap species.

## Reproduce

```bash
python scripts/run_inference_validation.py
pytest -q tests/test_inference_validation.py
```

Outputs in `results/inference_validation.*` are deterministic synthetic
evidence. Interpretation must retain that label.
