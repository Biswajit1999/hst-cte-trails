"""Pipeline orchestration composing the reusable scientific modules.

`run_pipeline` is the single non-notebook entry point for the real-data
analysis; scripts/run_analysis.py and notebooks/ both call into it rather
than reimplementing logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from hst_acs_two_axis_cte_audit.config import AnalysisConfig
from hst_acs_two_axis_cte_audit.exceptions import ConvergenceError, InsufficientDataError
from hst_acs_two_axis_cte_audit.fits_io import ExposureProduct, load_exposure
from hst_acs_two_axis_cte_audit.hot_pixels import detect_hot_pixels_from_dq
from hst_acs_two_axis_cte_audit.logging_utils import get_logger
from hst_acs_two_axis_cte_audit.stacking import ScalarBinningResult, bin_scalar_statistic
from hst_acs_two_axis_cte_audit.trail_profiles import (
    DetectedSource,
    SuppressionResult,
    TrailFitResult,
    compare_flt_flc_suppression,
    detect_sources,
    extract_parallel_trail,
    fit_exponential_trail,
)
from hst_acs_two_axis_cte_audit.uncertainty import bootstrap_statistic

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class Summary:
    count: int
    median: float
    mad: float


def validate_numeric(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError("values must be one-dimensional")
    if arr.size == 0:
        raise ValueError("values must not be empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError("values contain non-finite entries")
    return arr


def robust_summary(values: np.ndarray) -> Summary:
    arr = validate_numeric(values)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    return Summary(count=int(arr.size), median=median, mad=mad)


def demo_series(seed: int = 20260713, size: int = 128) -> np.ndarray:
    """Return deterministic synthetic data labelled only for smoke testing."""
    if size < 8:
        raise ValueError("size must be at least 8")
    rng = np.random.default_rng(seed)
    return rng.normal(loc=0.0, scale=1.0, size=size)


@dataclass(frozen=True)
class PairedExposure:
    rootname: str
    flt_path: Path
    flc_path: Path


def pair_flt_flc(manifest_rows: list[dict], raw_dir: str | Path) -> list[PairedExposure]:
    """Pair FLT/FLC files recorded in the manifest by their shared rootname."""
    raw_dir = Path(raw_dir)
    by_root: dict[str, dict[str, Path]] = {}
    for row in manifest_rows:
        product_id = row["product_id"]
        for suffix, kind in (("_flt", "flt"), ("_flc", "flc")):
            if product_id.endswith(suffix):
                root = product_id[: -len(suffix)]
                by_root.setdefault(root, {})[kind] = raw_dir / f"{product_id}.fits"

    pairs = [
        PairedExposure(rootname=root, flt_path=paths["flt"], flc_path=paths["flc"])
        for root, paths in sorted(by_root.items())
        if "flt" in paths and "flc" in paths
    ]
    if not pairs:
        raise InsufficientDataError("no FLT/FLC pairs found in manifest for the given raw_dir")
    return pairs


@dataclass(frozen=True)
class SourceMeasurement:
    rootname: str
    x: float
    y: float
    flux: float
    parallel_transfer_distance: float
    suppression: SuppressionResult


def _measure_pair(
    flt: ExposureProduct, flc: ExposureProduct, rootname: str, max_distance: int, brightest_sources: int
) -> tuple[list[SourceMeasurement], list[str]]:
    warnings: list[str] = []
    sources: list[DetectedSource] = detect_sources(flc.science_array, brightest=brightest_sources)

    measurements: list[SourceMeasurement] = []
    for source in sources:
        try:
            flt_profile = extract_parallel_trail(
                flt.science_array, flt.geometry, source.x, source.y, max_distance=max_distance
            )
            flc_profile = extract_parallel_trail(
                flc.science_array, flc.geometry, source.x, source.y, max_distance=max_distance
            )
            flt_fit: TrailFitResult = fit_exponential_trail(flt_profile)
            flc_fit: TrailFitResult = fit_exponential_trail(flc_profile)
            suppression = compare_flt_flc_suppression(flt_fit, flc_fit)
        except (InsufficientDataError, ConvergenceError) as exc:
            # Per-source fit failures (poor S/N, blending, cosmic-ray-contaminated
            # profiles) are expected on real data and must not abort the whole
            # pipeline; they are recorded, not silently dropped, per
            # docs/ERROR_HANDLING.md. This is distinct from the synthetic
            # injection-recovery validation gate failing, which is a hard stop
            # condition (see tests/test_trail_profiles.py).
            warnings.append(f"{rootname}: source at ({source.x:.1f},{source.y:.1f}) skipped: {exc}")
            continue

        transfer_distance = float(flt.geometry.parallel_transfer_distance(np.array([source.y]))[0])
        measurements.append(
            SourceMeasurement(
                rootname=rootname,
                x=source.x,
                y=source.y,
                flux=source.flux,
                parallel_transfer_distance=transfer_distance,
                suppression=suppression,
            )
        )
    return measurements, warnings


@dataclass(frozen=True)
class PipelineResult:
    measurements: list[SourceMeasurement]
    charge_bins: ScalarBinningResult
    distance_bins: ScalarBinningResult
    hot_pixel_mean_excess: float
    hot_pixel_ci_low: float
    hot_pixel_ci_high: float
    hot_pixel_sample_size: int
    warnings: list[str] = field(default_factory=list)


def run_pipeline(
    manifest_rows: list[dict],
    raw_dir: str | Path,
    config: AnalysisConfig,
    max_distance: int = 15,
    brightest_sources: int = 40,
    n_charge_bins: int = 3,
    n_distance_bins: int = 3,
) -> PipelineResult:
    """Run the full FLT-vs-FLC CTE trail audit over paired real exposures."""
    pairs = pair_flt_flc(manifest_rows, raw_dir)
    LOGGER.info("Processing %d FLT/FLC pairs", len(pairs))

    all_measurements: list[SourceMeasurement] = []
    all_warnings: list[str] = []
    hot_pixel_excess: list[float] = []

    for pair in pairs:
        flt = load_exposure(pair.flt_path)
        flc = load_exposure(pair.flc_path)

        measurements, warnings = _measure_pair(
            flt, flc, pair.rootname, max_distance=max_distance, brightest_sources=brightest_sources
        )
        all_measurements.extend(measurements)
        all_warnings.extend(warnings)

        try:
            catalog = detect_hot_pixels_from_dq(flt.dq_mask, flt.science_array)
            hot_pixel_excess.extend(catalog.excess_counts.tolist())
        except InsufficientDataError as exc:
            all_warnings.append(f"{pair.rootname}: hot pixel detection skipped: {exc}")

    if not all_measurements:
        raise InsufficientDataError("no usable source trail measurements across any FLT/FLC pair")

    fluxes = np.array([m.flux for m in all_measurements])
    distances = np.array([m.parallel_transfer_distance for m in all_measurements])
    suppression_fractions = np.array([m.suppression.suppression_fraction for m in all_measurements])

    charge_edges = np.quantile(fluxes, np.linspace(0, 1, n_charge_bins + 1))
    charge_edges[-1] += 1.0  # make the rightmost edge inclusive of the max
    charge_bins = bin_scalar_statistic(
        fluxes, suppression_fractions, charge_edges, config.validation.minimum_sample_size
    )

    distance_edges = np.quantile(distances, np.linspace(0, 1, n_distance_bins + 1))
    distance_edges[-1] += 1.0
    distance_bins = bin_scalar_statistic(
        distances, suppression_fractions, distance_edges, config.validation.minimum_sample_size
    )
    all_warnings.extend(charge_bins.warnings)
    all_warnings.extend(distance_bins.warnings)

    if len(hot_pixel_excess) >= 2:
        bootstrap_result = bootstrap_statistic(
            np.array(hot_pixel_excess),
            statistic=np.mean,
            n_resamples=config.validation.bootstrap_resamples,
            seed=config.execution.seed,
            confidence_level=config.validation.confidence_level,
        )
        mean, ci_low, ci_high = (
            bootstrap_result.estimate,
            bootstrap_result.ci_low,
            bootstrap_result.ci_high,
        )
    else:
        mean, ci_low, ci_high = float("nan"), float("nan"), float("nan")
        all_warnings.append("insufficient hot-pixel sample for bootstrap uncertainty")

    return PipelineResult(
        measurements=all_measurements,
        charge_bins=charge_bins,
        distance_bins=distance_bins,
        hot_pixel_mean_excess=mean,
        hot_pixel_ci_low=ci_low,
        hot_pixel_ci_high=ci_high,
        hot_pixel_sample_size=len(hot_pixel_excess),
        warnings=all_warnings,
    )
