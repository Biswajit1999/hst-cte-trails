"""Source detection and CTE trail-profile extraction/fitting.

Trails are modelled as a single empirical exponential decay,
`I(d) = amplitude * exp(-d / length) + offset`, in the pixels between a
source and the readout amplifier (see geometry.py for the direction
convention). This is the same empirical form used descriptively in Massey
et al. (2010, arXiv:0909.0507) and Anderson & Bedin (2010, arXiv:1007.3987);
it is not a multi-trap-species physical simulation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from astropy.stats import sigma_clipped_stats
from photutils.detection import DAOStarFinder
from scipy.optimize import curve_fit

from hst_acs_two_axis_cte_audit.exceptions import ConvergenceError, InsufficientDataError
from hst_acs_two_axis_cte_audit.geometry import AmpGeometry
from hst_acs_two_axis_cte_audit.uncertainty import FitConvergence, check_fit_convergence


def exponential_trail_model(d: np.ndarray, amplitude: float, length: float, offset: float) -> np.ndarray:
    return amplitude * np.exp(-np.asarray(d, dtype=float) / length) + offset


@dataclass(frozen=True)
class DetectedSource:
    x: float
    y: float
    flux: float


def detect_sources(
    science: np.ndarray,
    fwhm: float = 2.5,
    threshold_sigma: float = 8.0,
    brightest: int | None = None,
) -> list[DetectedSource]:
    """Detect point sources with photutils DAOStarFinder on a background-clipped image."""
    _, median, std = sigma_clipped_stats(science, sigma=3.0, maxiters=5)
    if std == 0:
        raise InsufficientDataError("background standard deviation is zero; cannot run source detection")

    finder = DAOStarFinder(threshold=threshold_sigma * std, fwhm=fwhm, brightest=brightest)
    table = finder(science - median)
    if table is None or len(table) == 0:
        raise InsufficientDataError(
            f"no sources detected above {threshold_sigma}-sigma threshold"
        )
    return [
        DetectedSource(x=float(row["xcentroid"]), y=float(row["ycentroid"]), flux=float(row["flux"]))
        for row in table
    ]


@dataclass(frozen=True)
class TrailProfile:
    distances: np.ndarray
    values: np.ndarray
    axis: str  # "parallel" or "serial"


def extract_parallel_trail(
    science: np.ndarray,
    geometry: AmpGeometry,
    source_x: float,
    source_y: float,
    max_distance: int = 15,
    min_distance: int = 4,
) -> TrailProfile:
    """Extract the 1-D profile along the parallel (row/readout) axis behind a source.

    `min_distance` skips pixels still inside the source's own PSF wings
    (default 4 px, matching the PSF core radius used elsewhere in this
    package); starting the trail measurement inside the PSF footprint biases
    the fitted amplitude and length, as PSF wing flux falls off on the same
    order of pixels as a short CTE trail.
    """
    x_i = int(round(source_x))
    y_i = int(round(source_y))
    direction = geometry.parallel_direction()
    distances = np.arange(min_distance, max_distance + 1)
    rows = y_i - direction * distances
    valid = (rows >= 0) & (rows < geometry.naxis2)
    rows, distances = rows[valid], distances[valid]
    if rows.size == 0:
        raise InsufficientDataError(
            "no valid pixels for parallel trail extraction (source adjacent to readout edge)"
        )
    if not (0 <= x_i < geometry.naxis1):
        raise InsufficientDataError(f"source x={x_i} is outside the array (naxis1={geometry.naxis1})")
    values = science[rows, x_i]
    return TrailProfile(distances=distances.astype(float), values=values.astype(float), axis="parallel")


def extract_serial_trail(
    science: np.ndarray,
    geometry: AmpGeometry,
    source_x: float,
    source_y: float,
    max_distance: int = 15,
    min_distance: int = 4,
) -> TrailProfile:
    """Extract the 1-D profile along the serial (column/readout) axis behind a source.

    See `extract_parallel_trail` for the rationale behind `min_distance`.
    """
    x_i = int(round(source_x))
    y_i = int(round(source_y))
    direction = geometry.serial_direction()
    distances = np.arange(min_distance, max_distance + 1)
    cols = x_i - direction * distances
    valid = (cols >= 0) & (cols < geometry.naxis1)
    cols, distances = cols[valid], distances[valid]
    if cols.size == 0:
        raise InsufficientDataError(
            "no valid pixels for serial trail extraction (source adjacent to readout edge)"
        )
    if not (0 <= y_i < geometry.naxis2):
        raise InsufficientDataError(f"source y={y_i} is outside the array (naxis2={geometry.naxis2})")
    values = science[y_i, cols]
    return TrailProfile(distances=distances.astype(float), values=values.astype(float), axis="serial")


@dataclass(frozen=True)
class TrailFitResult:
    amplitude: float
    length: float
    offset: float
    convergence: FitConvergence


def fit_exponential_trail(
    profile: TrailProfile,
    length_guess: float = 5.0,
    max_condition_number: float = 1e12,
) -> TrailFitResult:
    """Fit the exponential trail model, raising ConvergenceError on failure.

    Requires at least 4 points (3 free parameters + 1 degree of freedom).
    """
    if profile.distances.size < 4:
        raise InsufficientDataError(
            f"need at least 4 points to fit a 3-parameter exponential, got {profile.distances.size}"
        )
    if not np.all(np.isfinite(profile.values)):
        raise ConvergenceError("trail profile contains non-finite values; refusing to fit")

    amplitude_guess = float(profile.values[0] - np.median(profile.values))
    offset_guess = float(np.median(profile.values))
    p0 = [amplitude_guess if amplitude_guess != 0 else 1.0, length_guess, offset_guess]

    try:
        popt, pcov = curve_fit(
            exponential_trail_model, profile.distances, profile.values, p0=p0, maxfev=5000
        )
    except RuntimeError as exc:
        raise ConvergenceError(f"exponential trail fit failed to converge: {exc}") from exc

    residuals = profile.values - exponential_trail_model(profile.distances, *popt)
    dof = profile.distances.size - len(popt)
    convergence = check_fit_convergence(pcov, residuals=residuals, dof=dof, max_condition_number=max_condition_number)

    return TrailFitResult(
        amplitude=float(popt[0]), length=float(popt[1]), offset=float(popt[2]), convergence=convergence
    )


def total_trail_charge(fit: TrailFitResult) -> float:
    """Analytic total trailed charge: integral of amplitude*exp(-d/length) over d in [0, inf).

    Reported in the same units as the input science array (electrons for
    calibrated ACS/WFC products). This is the standard trailed-charge summary
    statistic used descriptively in the CTE literature seeds, not a
    trap-physics-derived quantity.
    """
    return float(fit.amplitude * fit.length)


@dataclass(frozen=True)
class SuppressionResult:
    flt_total_charge: float
    flc_total_charge: float
    suppression_fraction: float


SUPPRESSION_FRACTION_SANITY_BOUND = 3.0


def compare_flt_flc_suppression(flt_fit: TrailFitResult, flc_fit: TrailFitResult) -> SuppressionResult:
    """Fractional reduction in total trailed charge from FLT to FLC.

    suppression_fraction = 1 - (FLC total charge / FLT total charge); a value
    near 1 indicates near-complete pixel-based CTE correction, near 0
    indicates no measurable correction. Physically this should stay roughly
    within [-1, 1] (FLC trail charge between zero and up to ~2x the FLT
    value in a noisy worst case); a fit can pass the covariance-conditioning
    gate in `check_fit_convergence` yet still return a wildly unphysical
    amplitude/length combination (e.g. from a near-flat, noise-dominated
    profile). Values outside `SUPPRESSION_FRACTION_SANITY_BOUND` are treated
    as a fit-quality failure and raise ConvergenceError rather than being
    silently included in aggregate statistics, where a single such outlier
    can dominate a bin mean.
    """
    flt_total = total_trail_charge(flt_fit)
    flc_total = total_trail_charge(flc_fit)
    if flt_total == 0:
        raise InsufficientDataError("FLT total trail charge is zero; suppression fraction is undefined")
    suppression_fraction = float(1 - flc_total / flt_total)
    if not np.isfinite(suppression_fraction) or abs(suppression_fraction) > SUPPRESSION_FRACTION_SANITY_BOUND:
        raise ConvergenceError(
            f"suppression_fraction={suppression_fraction:.3g} is outside the physically plausible "
            f"range [-{SUPPRESSION_FRACTION_SANITY_BOUND}, {SUPPRESSION_FRACTION_SANITY_BOUND}]; "
            "treating as an unreliable fit rather than reporting it"
        )
    return SuppressionResult(
        flt_total_charge=flt_total,
        flc_total_charge=flc_total,
        suppression_fraction=suppression_fraction,
    )
