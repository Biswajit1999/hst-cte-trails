# Literature and calibration anchors

The following primary or official sources bound the interpretation of this repository.

- Anderson & Bedin (2010), *An Empirical Pixel-Based Correction for Imperfect CTE. I. HST's Advanced Camera for Surveys*, PASP 122, DOI 10.1086/656399.
- Massey et al. (2010), *Pixel-based correction for Charge Transfer Inefficiency in the Hubble Space Telescope Advanced Camera for Surveys*, MNRAS 401, arXiv:0909.0507.
- STScI, ACS Instrument Handbook, section 4.3.8, Charge Transfer Efficiency: <https://hst-docs.stsci.edu/acsihb/chapter-4-detector-performance/4-3-ccd-operations-and-limitations>.
- STScI, ACS Data Handbook, section 4.6, WFC CCD Detector Charge Transfer Efficiency: <https://hst-docs.stsci.edu/acsdhb/chapter-4-acs-data-processing-considerations/4-6-wfc-ccd-detector-charge-transfer-efficiency-cte>.
- CALACS 10.4.1 and the archive headers identify the current pixel-based correction and `PCTETAB=jref$8ch1518tj_cte.fits` used by all three FLC products.

## Verification requirement

The repository cites these sources for detector and pipeline context only. Its fitted one-dimensional exponential is a descriptive estimator and does not reproduce CALACS trap physics or validate the current PCTETAB.
