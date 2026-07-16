"""Hot/warm pixel detection, independent of point-source trail extraction.

Provides a DQ-mask-driven detector and a sigma-clipped statistical detector
as an independent cross-check, plus bootstrap uncertainty on the mean excess
signal, per docs/VALIDATION_CONTRACT.md ("bootstrap hot pixels").
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.stats import sigma_clipped_stats

from hst_acs_two_axis_cte_audit.exceptions import DataSchemaError, InsufficientDataError

DEFAULT_HOT_PIXEL_DQ_BIT = 16
"""ACS DQ bit for HOTPIX ("hot pixel"), verified against the official CALACS
source (spacetelescope/hstcal, pkg/acs/include/acsdq.h: HOTPIX = 16), not
assumed."""


@dataclass(frozen=True)
class HotPixelCatalog:
    y: np.ndarray
    x: np.ndarray
    excess_counts: np.ndarray
    background_median: float
    background_std: float


def _validate_shapes(dq_mask: np.ndarray, science: np.ndarray) -> None:
    if dq_mask.shape != science.shape:
        raise DataSchemaError(
            f"dq_mask shape {dq_mask.shape} does not match science shape {science.shape}"
        )


def detect_hot_pixels_from_dq(
    dq_mask: np.ndarray,
    science: np.ndarray,
    dq_bit: int = DEFAULT_HOT_PIXEL_DQ_BIT,
    sigma: float = 5.0,
) -> HotPixelCatalog:
    """Detect hot pixels via a DQ bit flag, reporting excess above local background."""
    _validate_shapes(dq_mask, science)
    if not np.all(np.isfinite(science)):
        raise DataSchemaError("science array contains non-finite values")

    flagged = (dq_mask.astype(np.int64) & dq_bit) != 0
    ys, xs = np.nonzero(flagged)
    if ys.size == 0:
        raise InsufficientDataError(f"no pixels flagged with DQ bit {dq_bit}")

    _, median, std = sigma_clipped_stats(science, sigma=sigma, maxiters=5)
    excess = science[ys, xs] - median
    return HotPixelCatalog(
        y=ys, x=xs, excess_counts=excess, background_median=float(median), background_std=float(std)
    )


def detect_hot_pixels_by_sigma_clip(
    science: np.ndarray,
    sigma: float = 5.0,
    minimum_sample_size: int = 1,
) -> HotPixelCatalog:
    """Independent statistical detector: pixels sigma above the clipped background.

    Used as a cross-check against DQ-mask-driven detection, not as a
    replacement for it.
    """
    if not np.all(np.isfinite(science)):
        raise DataSchemaError("science array contains non-finite values")

    _, median, std = sigma_clipped_stats(science, sigma=sigma, maxiters=5)
    if std == 0:
        raise InsufficientDataError("background standard deviation is zero; cannot threshold")

    threshold = median + sigma * std
    ys, xs = np.nonzero(science > threshold)
    if ys.size < minimum_sample_size:
        raise InsufficientDataError(
            f"only {ys.size} sigma-clipped hot-pixel candidates found, "
            f"below minimum_sample_size={minimum_sample_size}"
        )
    excess = science[ys, xs] - median
    return HotPixelCatalog(
        y=ys, x=xs, excess_counts=excess, background_median=float(median), background_std=float(std)
    )


def bootstrap_mean_excess(
    catalog: HotPixelCatalog,
    n_resamples: int,
    seed: int,
    confidence_level: float = 0.95,
) -> tuple[float, float, float]:
    """Bootstrap the mean hot-pixel excess signal.

    Returns (mean, ci_low, ci_high). Raises InsufficientDataError if the
    catalog is too small to bootstrap meaningfully.
    """
    if catalog.excess_counts.size < 2:
        raise InsufficientDataError(
            f"catalog has only {catalog.excess_counts.size} entries; cannot bootstrap"
        )
    rng = np.random.default_rng(seed)
    n = catalog.excess_counts.size
    resampled_means = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        resampled_means[i] = np.mean(catalog.excess_counts[idx])

    alpha = 1 - confidence_level
    ci_low, ci_high = np.percentile(resampled_means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(np.mean(catalog.excess_counts)), float(ci_low), float(ci_high)
