from __future__ import annotations

import numpy as np
import pytest

from hst_acs_two_axis_cte_audit.exceptions import DataSchemaError, InsufficientDataError
from hst_acs_two_axis_cte_audit.hot_pixels import (
    DEFAULT_HOT_PIXEL_DQ_BIT,
    bootstrap_mean_excess,
    detect_hot_pixels_by_sigma_clip,
    detect_hot_pixels_from_dq,
)


def _synthetic_field(seed=20260713, shape=(60, 60), background=20.0, n_hot=8, hot_excess=300.0):
    rng = np.random.default_rng(seed)
    science = rng.normal(background, 3.0, size=shape)
    dq = np.zeros(shape, dtype=np.int16)
    hot_rng = np.random.default_rng(seed + 1)
    ys = hot_rng.choice(shape[0], size=n_hot, replace=False)
    xs = hot_rng.choice(shape[1], size=n_hot, replace=False)
    for y, x in zip(ys, xs):
        science[y, x] += hot_excess
        dq[y, x] = DEFAULT_HOT_PIXEL_DQ_BIT
    return science, dq, hot_excess


def test_detect_hot_pixels_from_dq_finds_injected_pixels():
    science, dq, hot_excess = _synthetic_field()
    catalog = detect_hot_pixels_from_dq(dq, science)
    assert catalog.y.size == 8
    assert np.all(catalog.excess_counts > hot_excess * 0.5)


def test_detect_hot_pixels_from_dq_raises_when_no_flags():
    science, _, _ = _synthetic_field()
    dq = np.zeros_like(science, dtype=np.int16)
    with pytest.raises(InsufficientDataError):
        detect_hot_pixels_from_dq(dq, science)


def test_detect_hot_pixels_shape_mismatch_raises_schema_error():
    science = np.zeros((10, 10))
    dq = np.zeros((5, 5), dtype=np.int16)
    with pytest.raises(DataSchemaError):
        detect_hot_pixels_from_dq(dq, science)


def test_sigma_clip_detector_agrees_with_dq_detector_roughly():
    science, dq, _ = _synthetic_field()
    dq_catalog = detect_hot_pixels_from_dq(dq, science)
    sigma_catalog = detect_hot_pixels_by_sigma_clip(science, sigma=5.0)
    dq_pixels = set(zip(dq_catalog.y.tolist(), dq_catalog.x.tolist()))
    sigma_pixels = set(zip(sigma_catalog.y.tolist(), sigma_catalog.x.tolist()))
    assert dq_pixels.issubset(sigma_pixels) or len(dq_pixels & sigma_pixels) >= 6


def test_bootstrap_mean_excess_ci_covers_true_excess():
    science, dq, hot_excess = _synthetic_field(n_hot=40)
    catalog = detect_hot_pixels_from_dq(dq, science)
    mean, ci_low, ci_high = bootstrap_mean_excess(catalog, n_resamples=1000, seed=20260713)
    assert ci_low < hot_excess < ci_high


def test_bootstrap_mean_excess_requires_at_least_two_pixels():
    from hst_acs_two_axis_cte_audit.hot_pixels import HotPixelCatalog

    catalog = HotPixelCatalog(
        y=np.array([1]), x=np.array([1]), excess_counts=np.array([100.0]), background_median=0.0, background_std=1.0
    )
    with pytest.raises(InsufficientDataError):
        bootstrap_mean_excess(catalog, n_resamples=100, seed=1)
