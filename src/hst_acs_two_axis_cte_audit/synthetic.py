"""Synthetic ACS/WFC-like data generation, clearly labelled and never real data.

Shared by both the test suite (injection-recovery validation) and
`scripts/make_figures.py --demo` / `scripts/run_analysis.py --demo`, so the
synthetic-data model is implemented once rather than duplicated between
tests and demo scripts.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.io import fits

DEFAULT_HOT_PIXEL_DQ_BIT = 16


@dataclass(frozen=True)
class SyntheticSource:
    x: int
    y: int
    flux: float


@dataclass(frozen=True)
class SyntheticTrailSpec:
    amplitude_fraction: float
    length_pixels: float


def build_synthetic_acs_hdulist(
    *,
    seed: int = 20260713,
    naxis1: int = 100,
    naxis2: int = 120,
    ccdchip: int = 1,
    ccdamp: str = "C",
    exptime: float = 460.0,
    ccdgain: float = 2.0,
    background: float = 20.0,
    read_noise: float = 4.0,
    sources: tuple[SyntheticSource, ...] = (SyntheticSource(50, 90, 6000.0),),
    parallel_trail: SyntheticTrailSpec | None = SyntheticTrailSpec(0.02, 6.0),
    serial_trail: SyntheticTrailSpec | None = SyntheticTrailSpec(0.01, 3.0),
    inject_hot_pixels: int = 5,
) -> fits.HDUList:
    """Build a minimal, labelled-synthetic ACS/WFC-style HDUList.

    Amplifier is assumed to sit at row 0 (CCDAMP in {'C', 'D'}) or row
    naxis2-1 (CCDAMP in {'A', 'B'}); trails are injected on the amp-side of
    each source (between the source and the readout register), matching the
    documented, explicit convention in docs/ASSUMPTIONS_AND_LIMITATIONS.md.
    This is a simplified single-exponential empirical model, not a
    trap-physics simulation, and is only used to give synthetic-injection
    tests and demo figures a known ground truth. Never presented as an
    observation.
    """
    rng = np.random.default_rng(seed)

    science = rng.normal(loc=background, scale=read_noise, size=(naxis2, naxis1)).astype(np.float32)
    dq = np.zeros((naxis2, naxis1), dtype=np.int16)

    readout_row = 0 if ccdamp in ("C", "D") else naxis2 - 1

    psf_fwhm = 2.5
    psf_sigma = psf_fwhm / 2.3548
    half_box = 4
    yy, xx = np.mgrid[-half_box : half_box + 1, -half_box : half_box + 1]
    psf_kernel = np.exp(-(xx**2 + yy**2) / (2 * psf_sigma**2))
    psf_kernel /= psf_kernel.sum()

    for src in sources:
        # Inject a Gaussian PSF core (not a bare delta-function pixel) so that
        # DAOStarFinder's sharpness/roundness shape filters — which exist
        # precisely to reject single-pixel spikes such as cosmic rays and hot
        # pixels — correctly accept this as a real point source.
        y0, y1 = src.y - half_box, src.y + half_box + 1
        x0, x1 = src.x - half_box, src.x + half_box + 1
        cy0, cy1 = max(0, -y0), psf_kernel.shape[0] - max(0, y1 - naxis2)
        cx0, cx1 = max(0, -x0), psf_kernel.shape[1] - max(0, x1 - naxis1)
        science[max(0, y0) : min(naxis2, y1), max(0, x0) : min(naxis1, x1)] += (
            src.flux * psf_kernel[cy0:cy1, cx0:cx1]
        )

        if parallel_trail is not None:
            direction = 1 if readout_row == 0 else -1
            distance = np.arange(1, abs(src.y - readout_row) + 1)
            rows = src.y - direction * distance
            valid = (rows >= 0) & (rows < naxis2)
            trail_values = src.flux * parallel_trail.amplitude_fraction * np.exp(
                -distance[valid] / parallel_trail.length_pixels
            )
            science[rows[valid], src.x] += trail_values

        if serial_trail is not None:
            readout_col = 0 if ccdamp in ("C", "A") else naxis1 - 1
            direction = 1 if readout_col == 0 else -1
            distance = np.arange(1, abs(src.x - readout_col) + 1)
            cols = src.x - direction * distance
            valid = (cols >= 0) & (cols < naxis1)
            trail_values = src.flux * serial_trail.amplitude_fraction * np.exp(
                -distance[valid] / serial_trail.length_pixels
            )
            science[src.y, cols[valid]] += trail_values

    hot_rng = np.random.default_rng(seed + 1)
    for _ in range(inject_hot_pixels):
        hy = int(hot_rng.integers(0, naxis2))
        hx = int(hot_rng.integers(0, naxis1))
        science[hy, hx] += float(hot_rng.uniform(500, 2000))
        dq[hy, hx] = DEFAULT_HOT_PIXEL_DQ_BIT

    err = np.sqrt(np.clip(science, 1.0, None) / ccdgain + read_noise**2).astype(np.float32)

    primary_header = fits.Header()
    primary_header["INSTRUME"] = "ACS"
    primary_header["DETECTOR"] = "WFC"
    primary_header["EXPTIME"] = exptime
    primary_header["CCDGAIN"] = ccdgain
    primary_header["SUBARRAY"] = False
    primary_header["FILTER1"] = "CLEAR1L"
    primary_header["FILTER2"] = "F606W"
    primary_header["ROOTNAME"] = "synthetic0"

    sci_header = fits.Header()
    sci_header["CCDCHIP"] = ccdchip
    sci_header["CCDAMP"] = ccdamp
    sci_header["EXTNAME"] = "SCI"
    sci_header["EXTVER"] = 1
    sci_header["BUNIT"] = "ELECTRONS"

    hdul = fits.HDUList(
        [
            fits.PrimaryHDU(header=primary_header),
            fits.ImageHDU(data=science, header=sci_header, name="SCI"),
            fits.ImageHDU(data=err, header=sci_header.copy(), name="ERR"),
            fits.ImageHDU(data=dq, header=sci_header.copy(), name="DQ"),
        ]
    )
    return hdul
