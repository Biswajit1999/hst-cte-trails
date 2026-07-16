from __future__ import annotations

import numpy as np
import pytest

from hst_acs_two_axis_cte_audit.exceptions import ConvergenceError, InsufficientDataError
from hst_acs_two_axis_cte_audit.uncertainty import bootstrap_statistic, check_fit_convergence


def test_bootstrap_ci_matches_analytic_standard_error():
    # A single finite sample's bootstrap CI is not guaranteed to bracket the
    # true population mean (that only holds ~95% of the time by
    # construction), so this checks the bootstrap machinery itself: the
    # reported CI should agree with the analytic normal-approximation CI for
    # the sample mean, and should bracket the sample's own mean.
    rng = np.random.default_rng(20260713)
    data = rng.normal(loc=5.0, scale=1.0, size=500)
    sample_mean = np.mean(data)
    analytic_half_width = 1.96 * np.std(data, ddof=1) / np.sqrt(data.size)

    result = bootstrap_statistic(data, np.mean, n_resamples=2000, seed=20260713, confidence_level=0.95)

    assert result.ci_low < sample_mean < result.ci_high
    bootstrap_half_width = (result.ci_high - result.ci_low) / 2
    assert bootstrap_half_width == pytest.approx(analytic_half_width, rel=0.25)


def test_bootstrap_requires_at_least_two_samples():
    with pytest.raises(InsufficientDataError):
        bootstrap_statistic(np.array([1.0]), np.mean, n_resamples=100, seed=1)


def test_bootstrap_rejects_invalid_confidence_level():
    with pytest.raises(ValueError):
        bootstrap_statistic(np.array([1.0, 2.0, 3.0]), np.mean, n_resamples=100, seed=1, confidence_level=1.5)


def test_check_fit_convergence_accepts_well_conditioned_covariance():
    pcov = np.diag([1.0, 1.0, 1.0])
    result = check_fit_convergence(pcov, residuals=np.array([0.1, -0.1, 0.05]), dof=1)
    assert result.converged
    assert result.reduced_chi_square is not None


def test_check_fit_convergence_rejects_non_finite_covariance():
    pcov = np.array([[1.0, np.nan], [np.nan, 1.0]])
    with pytest.raises(ConvergenceError):
        check_fit_convergence(pcov)


def test_check_fit_convergence_rejects_ill_conditioned_covariance():
    pcov = np.array([[1e20, 0.0], [0.0, 1e-20]])
    with pytest.raises(ConvergenceError):
        check_fit_convergence(pcov, max_condition_number=1e10)
