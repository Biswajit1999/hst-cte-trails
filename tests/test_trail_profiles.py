"""Synthetic injection-recovery validation gate.

Per docs/VALIDATION_CONTRACT.md and the CLAUDE_TASK.md stop condition: if
this recovery test fails, the pipeline must not be used to interpret real
data as validated. Thresholds below were calibrated empirically across 15
independent noise realizations (see IMPLEMENTATION_PLAN.md) at this
signal-to-noise level, where the observed worst case was ~7% amplitude error
and ~11% length error; the thresholds here are set with margin above that.
"""
from __future__ import annotations

import numpy as np
import pytest

from hst_acs_two_axis_cte_audit.exceptions import ConvergenceError, InsufficientDataError
from hst_acs_two_axis_cte_audit.geometry import infer_geometry
from hst_acs_two_axis_cte_audit.trail_profiles import (
    TrailFitResult,
    TrailProfile,
    compare_flt_flc_suppression,
    exponential_trail_model,
    extract_parallel_trail,
    fit_exponential_trail,
    total_trail_charge,
)
from hst_acs_two_axis_cte_audit.uncertainty import FitConvergence
from conftest import SyntheticSource, SyntheticTrailSpec, build_synthetic_acs_hdulist

AMPLITUDE_TOLERANCE = 0.15
LENGTH_TOLERANCE = 0.25


def test_synthetic_exponential_trail_recovery():
    source = SyntheticSource(50, 90, 20000.0)
    trail_spec = SyntheticTrailSpec(amplitude_fraction=0.05, length_pixels=6.0)
    hdul = build_synthetic_acs_hdulist(
        sources=(source,), parallel_trail=trail_spec, serial_trail=None, inject_hot_pixels=0
    )
    geometry = infer_geometry(dict(hdul["SCI"].header) | dict(hdul[0].header))

    profile = extract_parallel_trail(hdul["SCI"].data, geometry, source.x, source.y)
    fit = fit_exponential_trail(profile)

    truth_amplitude = source.flux * trail_spec.amplitude_fraction
    amplitude_error = abs(fit.amplitude - truth_amplitude) / truth_amplitude
    length_error = abs(fit.length - trail_spec.length_pixels) / trail_spec.length_pixels

    assert amplitude_error < AMPLITUDE_TOLERANCE, f"amplitude recovery error {amplitude_error:.1%} too large"
    assert length_error < LENGTH_TOLERANCE, f"length recovery error {length_error:.1%} too large"
    assert fit.convergence.converged


def test_total_trail_charge_is_positive_for_positive_amplitude():
    # A tiny amount of noise is added because perfectly noiseless data drives
    # curve_fit's residual variance to exactly zero, which makes the reported
    # covariance singular (infinite condition number) even though the fit
    # itself is essentially exact — not a realistic scenario for real data.
    rng = np.random.default_rng(20260713)
    distances = np.arange(1.0, 10.0)
    values = exponential_trail_model(distances, 100.0, 5.0, 20.0) + rng.normal(0.0, 0.1, size=distances.size)
    profile = TrailProfile(distances=distances, values=values, axis="parallel")
    fit = fit_exponential_trail(profile)
    assert total_trail_charge(fit) > 0


def test_null_control_zero_trail_amplitude_consistent_with_zero():
    """Negative control: a flat (no-trail) profile should fit an amplitude near zero."""
    rng = np.random.default_rng(20260713)
    distances = np.arange(4.0, 15.0)
    noise_sigma = 2.0
    values = 20.0 + rng.normal(0.0, noise_sigma, size=distances.size)
    profile = TrailProfile(distances=distances, values=values, axis="parallel")

    fit = fit_exponential_trail(profile)

    assert abs(fit.amplitude) < 10 * noise_sigma


def test_fit_rejects_too_few_points():
    profile = TrailProfile(distances=np.array([1.0, 2.0, 3.0]), values=np.array([10.0, 8.0, 6.0]), axis="parallel")
    with pytest.raises(InsufficientDataError):
        fit_exponential_trail(profile)


def test_fit_rejects_non_finite_values():
    distances = np.arange(1.0, 10.0)
    values = np.full_like(distances, np.nan)
    profile = TrailProfile(distances=distances, values=values, axis="parallel")
    with pytest.raises(ConvergenceError):
        fit_exponential_trail(profile)


def test_extract_parallel_trail_rejects_source_outside_array():
    geometry = infer_geometry({"NAXIS1": 20, "NAXIS2": 20, "CCDCHIP": 1, "CCDAMP": "C"})
    science = np.zeros((20, 20))
    with pytest.raises(InsufficientDataError):
        extract_parallel_trail(science, geometry, source_x=100, source_y=10)


def _fake_fit(amplitude: float, length: float) -> TrailFitResult:
    return TrailFitResult(
        amplitude=amplitude, length=length, offset=0.0,
        convergence=FitConvergence(converged=True, covariance_condition_number=1.0, reduced_chi_square=1.0),
    )


def test_compare_flt_flc_suppression_reasonable_values():
    result = compare_flt_flc_suppression(_fake_fit(1000.0, 6.0), _fake_fit(200.0, 6.0))
    assert result.suppression_fraction == pytest.approx(0.8)


def test_compare_flt_flc_suppression_rejects_unphysical_outlier():
    # A pathological fit (near-zero FLT amplitude, large FLC amplitude) can
    # pass the covariance-conditioning gate yet yield a suppression fraction
    # far outside [-3, 3]; this must be treated as a fit failure, not
    # reported, since a single such outlier would otherwise dominate any
    # aggregate (mean) statistic computed over many sources.
    with pytest.raises(ConvergenceError):
        compare_flt_flc_suppression(_fake_fit(10.0, 6.0), _fake_fit(500.0, 6.0))
