# Dataset Plan

## Mode

**real public HST ACS/WFC FLT/FLC products**

## Official sources and literature seeds

- Anderson & Bedin ACS/WFC pixel correction, arXiv:1007.3987
- Massey et al. ACS CTI correction, arXiv:0909.0507
- STScI ACS Data Handbook
- STScI CALACS documentation
- Recent ACS serial/parallel CTE calibration literature

## Acquisition rules

- Prefer official mission/archive endpoints and author-maintained catalogue deposits.
- Record product identifier, query, retrieval UTC, source URL, file size, checksum and licence/terms.
- Do not commit large raw FITS, HDF5 or catalogue files.
- Store a deterministic manifest under `data/manifest.csv`.
- Store only a tiny, clearly labelled synthetic/example dataset in `data/example/`.
- Never replace inaccessible real data with fabricated values while presenting them as observations.

## Required manifest columns

`product_id, source, source_url, retrieved_utc, sha256, file_size_bytes, selection_reason, licence_or_terms`

## FAIR contract

Every derived product must point to the raw product ID, software commit, configuration hash and transformation script.
