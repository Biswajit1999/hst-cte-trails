"""Synthetic validation of exponential CTE-trail inference.

The experiments in this module use generated one-dimensional profiles with
known parameters.  They validate estimator behaviour and do not alter or
reinterpret the published HST/ACS measurements.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
from scipy.optimize import curve_fit

from hst_acs_two_axis_cte_audit.trail_profiles import exponential_trail_model


@dataclass(frozen=True)
class WeightedTrailFit:
    amplitude_electrons: float
    length_pixels: float
    offset_electrons: float
    amplitude_sigma: float
    length_sigma: float
    offset_sigma: float
    reduced_chi_square: float


def fit_weighted_exponential(
    distances_pixels: np.ndarray,
    values_electrons: np.ndarray,
    sigma_electrons: np.ndarray,
) -> WeightedTrailFit:
    """Fit a positive-amplitude exponential with absolute 1-sigma errors."""
    distance = np.asarray(distances_pixels, dtype=float)
    values = np.asarray(values_electrons, dtype=float)
    sigma = np.asarray(sigma_electrons, dtype=float)
    if not (distance.shape == values.shape == sigma.shape) or distance.size < 5:
        raise ValueError("distance, values, and sigma must have the same shape and at least 5 points")
    if not np.all(np.isfinite(distance)) or not np.all(np.isfinite(values)):
        raise ValueError("profile contains non-finite values")
    if not np.all(np.isfinite(sigma)) or np.any(sigma <= 0):
        raise ValueError("all profile uncertainties must be finite and positive")
    offset = float(np.median(values[-max(3, distance.size // 3) :]))
    amplitude = max(float(values[0] - offset), float(np.median(sigma)))
    popt, covariance = curve_fit(
        exponential_trail_model,
        distance,
        values,
        p0=(amplitude, 5.0, offset),
        sigma=sigma,
        absolute_sigma=True,
        bounds=([0.0, 0.25, -np.inf], [np.inf, 50.0, np.inf]),
        maxfev=10_000,
    )
    errors = np.sqrt(np.diag(covariance))
    residual = (values - exponential_trail_model(distance, *popt)) / sigma
    reduced_chi_square = float(np.sum(residual**2) / (distance.size - 3))
    return WeightedTrailFit(
        amplitude_electrons=float(popt[0]),
        length_pixels=float(popt[1]),
        offset_electrons=float(popt[2]),
        amplitude_sigma=float(errors[0]),
        length_sigma=float(errors[1]),
        offset_sigma=float(errors[2]),
        reduced_chi_square=reduced_chi_square,
    )


def coverage_experiment(
    *,
    trials: int = 600,
    seed: int = 20261011,
    noise_electrons: float = 5.0,
    amplitude_electrons: float = 800.0,
    length_pixels: float = 6.0,
    offset_electrons: float = 20.0,
) -> dict[str, float]:
    """Estimate nominal 95% Wald-interval coverage on synthetic profiles."""
    if trials < 20 or noise_electrons <= 0:
        raise ValueError("trials must be >=20 and noise positive")
    distance = np.arange(4.0, 16.0)
    sigma = np.full(distance.shape, noise_electrons)
    truth = exponential_trail_model(distance, amplitude_electrons, length_pixels, offset_electrons)
    rng = np.random.default_rng(seed)
    amplitude_covered = 0
    length_covered = 0
    fitted = 0
    chi_square = []
    for _ in range(trials):
        values = truth + rng.normal(0.0, sigma)
        try:
            fit = fit_weighted_exponential(distance, values, sigma)
        except (RuntimeError, ValueError):
            continue
        fitted += 1
        amplitude_covered += abs(fit.amplitude_electrons - amplitude_electrons) <= 1.96 * fit.amplitude_sigma
        length_covered += abs(fit.length_pixels - length_pixels) <= 1.96 * fit.length_sigma
        chi_square.append(fit.reduced_chi_square)
    return {
        "trials": trials,
        "successful_fits": fitted,
        "fit_failure_fraction": (trials - fitted) / trials,
        "amplitude_95pct_coverage": amplitude_covered / fitted,
        "length_95pct_coverage": length_covered / fitted,
        "median_reduced_chi_square": float(np.median(chi_square)),
    }


def window_sensitivity_experiment(
    *,
    starts: Iterable[int] = (2, 3, 4, 5, 6),
    stops: Iterable[int] = (12, 15, 18, 22),
    trials: int = 160,
    seed: int = 20261012,
) -> list[dict[str, float]]:
    """Measure amplitude/length bias as the fitted pixel window changes.

    A short PSF-wing contaminant is injected alongside a 6-pixel CTE trail.
    This intentionally tests the documented reason for excluding the first
    few pixels behind a source.
    """
    rng = np.random.default_rng(seed)
    rows = []
    amplitude_true, length_true, offset, sigma = 800.0, 6.0, 20.0, 5.0
    for start in starts:
        for stop in stops:
            if stop - start + 1 < 6:
                continue
            distance = np.arange(float(start), float(stop + 1))
            cte = exponential_trail_model(distance, amplitude_true, length_true, offset)
            psf_wing = 500.0 * np.exp(-distance / 1.2)
            amplitude_biases = []
            length_biases = []
            for _ in range(trials):
                values = cte + psf_wing + rng.normal(0.0, sigma, distance.size)
                fit = fit_weighted_exponential(distance, values, np.full(distance.shape, sigma))
                amplitude_biases.append((fit.amplitude_electrons - amplitude_true) / amplitude_true)
                length_biases.append((fit.length_pixels - length_true) / length_true)
            rows.append(
                {
                    "start_pixel": int(start),
                    "stop_pixel": int(stop),
                    "median_amplitude_bias_fraction": float(np.median(amplitude_biases)),
                    "median_length_bias_fraction": float(np.median(length_biases)),
                }
            )
    return rows


def model_misspecification_experiment(
    slow_component_fractions: Iterable[float] = (0.0, 0.05, 0.10, 0.20, 0.35, 0.50),
    *,
    trials: int = 180,
    seed: int = 20261013,
) -> list[dict[str, float]]:
    """Fit a single exponential to two-component synthetic trap release.

    The reported total-charge bias exposes when the empirical one-component
    model is insufficient; it does not infer physical ACS trap populations.
    """
    distance = np.arange(4.0, 23.0)
    sigma = np.full(distance.shape, 4.0)
    rng = np.random.default_rng(seed)
    fast_amplitude, fast_length, slow_length, offset = 700.0, 3.0, 12.0, 15.0
    rows = []
    for fraction in slow_component_fractions:
        if not 0 <= fraction <= 1:
            raise ValueError("slow-component fractions must be in [0, 1]")
        slow_amplitude = fast_amplitude * float(fraction)
        truth = (
            fast_amplitude * np.exp(-distance / fast_length)
            + slow_amplitude * np.exp(-distance / slow_length)
            + offset
        )
        true_total = fast_amplitude * fast_length + slow_amplitude * slow_length
        charge_biases = []
        reduced_chi_square = []
        for _ in range(trials):
            values = truth + rng.normal(0.0, sigma)
            fit = fit_weighted_exponential(distance, values, sigma)
            fitted_total = fit.amplitude_electrons * fit.length_pixels
            charge_biases.append((fitted_total - true_total) / true_total)
            reduced_chi_square.append(fit.reduced_chi_square)
        rows.append(
            {
                "slow_amplitude_fraction": float(fraction),
                "median_total_charge_bias_fraction": float(np.median(charge_biases)),
                "median_reduced_chi_square": float(np.median(reduced_chi_square)),
            }
        )
    return rows


def serialise_fit(fit: WeightedTrailFit) -> dict[str, float]:
    return asdict(fit)
