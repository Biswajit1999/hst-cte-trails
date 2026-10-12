import numpy as np

from hst_acs_two_axis_cte_audit.inference_validation import (
    coverage_experiment,
    fit_weighted_exponential,
    model_misspecification_experiment,
    window_sensitivity_experiment,
)
from hst_acs_two_axis_cte_audit.trail_profiles import exponential_trail_model


def test_weighted_fit_recovers_known_profile():
    distance = np.arange(4.0, 20.0)
    sigma = np.full(distance.shape, 2.0)
    truth = exponential_trail_model(distance, 500.0, 5.0, 12.0)
    values = truth + np.random.default_rng(7).normal(0.0, sigma)
    fit = fit_weighted_exponential(distance, values, sigma)
    assert abs(fit.amplitude_electrons - 500.0) < 3 * fit.amplitude_sigma
    assert abs(fit.length_pixels - 5.0) < 3 * fit.length_sigma
    assert 0.2 < fit.reduced_chi_square < 3.0


def test_nominal_intervals_have_reasonable_seeded_coverage():
    result = coverage_experiment(trials=400)
    assert result["fit_failure_fraction"] == 0
    assert 0.90 <= result["amplitude_95pct_coverage"] <= 0.99
    assert 0.90 <= result["length_95pct_coverage"] <= 0.99
    assert 0.75 <= result["median_reduced_chi_square"] <= 1.25


def test_window_sweep_exposes_psf_wing_bias():
    rows = window_sensitivity_experiment(starts=(2, 4, 6), stops=(15,), trials=80)
    by_start = {row["start_pixel"]: row for row in rows}
    assert abs(by_start[6]["median_length_bias_fraction"]) < abs(by_start[2]["median_length_bias_fraction"])


def test_two_component_trails_break_single_exponential_charge_model():
    rows = model_misspecification_experiment((0.0, 0.5), trials=100)
    assert abs(rows[0]["median_total_charge_bias_fraction"]) < 0.05
    assert abs(rows[1]["median_total_charge_bias_fraction"]) > 0.05
    assert rows[1]["median_reduced_chi_square"] > rows[0]["median_reduced_chi_square"]
