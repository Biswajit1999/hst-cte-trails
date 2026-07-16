"""Stacking and binning of trail profiles for signal-to-noise improvement.

Bins that fall below the configured minimum sample size are reported with an
explicit warning rather than silently dropped, per docs/ERROR_HANDLING.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from hst_acs_two_axis_cte_audit.exceptions import InsufficientDataError
from hst_acs_two_axis_cte_audit.trail_profiles import TrailProfile


@dataclass(frozen=True)
class StackedProfile:
    distances: np.ndarray
    mean_values: np.ndarray
    std_values: np.ndarray
    n_stacked: int


def stack_profiles(profiles: list[TrailProfile]) -> StackedProfile:
    """Mean/std-stack a list of same-axis, same-distance-grid trail profiles."""
    if not profiles:
        raise InsufficientDataError("no profiles provided to stack")

    axis_set = {p.axis for p in profiles}
    if len(axis_set) > 1:
        raise InsufficientDataError(f"cannot stack profiles from different axes: {sorted(axis_set)}")

    reference = profiles[0].distances
    for profile in profiles[1:]:
        if profile.distances.shape != reference.shape or not np.array_equal(profile.distances, reference):
            raise InsufficientDataError(
                "profiles have mismatched distance grids; align them (e.g. via a common max_distance) before stacking"
            )

    stacked_values = np.stack([p.values for p in profiles])
    std = stacked_values.std(axis=0, ddof=1) if len(profiles) > 1 else np.zeros_like(reference)
    return StackedProfile(
        distances=reference, mean_values=stacked_values.mean(axis=0), std_values=std, n_stacked=len(profiles)
    )


@dataclass(frozen=True)
class BinnedStack:
    bin_low: float
    bin_high: float
    stacked: StackedProfile | None
    n_members: int
    underpopulated: bool


@dataclass(frozen=True)
class BinningResult:
    bins: list[BinnedStack]
    warnings: list[str] = field(default_factory=list)


def bin_and_stack(
    keys: np.ndarray,
    profiles: list[TrailProfile],
    edges: np.ndarray,
    minimum_sample_size: int,
) -> BinningResult:
    """Group profiles into bins of `keys` (e.g. source flux or transfer distance) and stack each bin.

    Bins with fewer than `minimum_sample_size` members are still returned
    (stacked if n_members >= 1, else stacked=None) but flagged via
    `underpopulated=True` and a message in `BinningResult.warnings`, matching
    the "never silently drop" rule in docs/ERROR_HANDLING.md.
    """
    keys = np.asarray(keys, dtype=float)
    if keys.shape[0] != len(profiles):
        raise InsufficientDataError(
            f"keys length {keys.shape[0]} does not match number of profiles {len(profiles)}"
        )
    edges = np.asarray(edges, dtype=float)
    if edges.ndim != 1 or edges.size < 2:
        raise InsufficientDataError("edges must be a 1-D array with at least 2 values")

    bin_indices = np.digitize(keys, edges) - 1
    bins: list[BinnedStack] = []
    warnings: list[str] = []

    for i in range(edges.size - 1):
        low, high = float(edges[i]), float(edges[i + 1])
        members = [p for p, idx in zip(profiles, bin_indices) if idx == i]
        n_members = len(members)
        underpopulated = n_members < minimum_sample_size

        if underpopulated:
            warnings.append(
                f"bin [{low:.3g}, {high:.3g}) has {n_members} members, "
                f"below minimum_sample_size={minimum_sample_size}"
            )

        stacked = stack_profiles(members) if n_members >= 1 else None
        bins.append(
            BinnedStack(bin_low=low, bin_high=high, stacked=stacked, n_members=n_members, underpopulated=underpopulated)
        )

    return BinningResult(bins=bins, warnings=warnings)


@dataclass(frozen=True)
class ScalarBin:
    bin_low: float
    bin_high: float
    mean: float
    std: float
    n_members: int
    underpopulated: bool


@dataclass(frozen=True)
class ScalarBinningResult:
    bins: list[ScalarBin]
    warnings: list[str] = field(default_factory=list)


def bin_scalar_statistic(
    keys: np.ndarray,
    values: np.ndarray,
    edges: np.ndarray,
    minimum_sample_size: int,
) -> ScalarBinningResult:
    """Bin scalar `values` (e.g. per-source suppression fraction) by scalar `keys`
    (e.g. source charge or transfer distance), reporting mean/std per bin.

    Used for the "suppression vs charge" and "residual vs transfer distance"
    figures, as distinct from `bin_and_stack`, which stacks full pixel-level
    trail profiles rather than one scalar per source.
    """
    keys = np.asarray(keys, dtype=float)
    values = np.asarray(values, dtype=float)
    if keys.shape != values.shape:
        raise InsufficientDataError(f"keys shape {keys.shape} does not match values shape {values.shape}")
    edges = np.asarray(edges, dtype=float)
    if edges.ndim != 1 or edges.size < 2:
        raise InsufficientDataError("edges must be a 1-D array with at least 2 values")

    bin_indices = np.digitize(keys, edges) - 1
    bins: list[ScalarBin] = []
    warnings: list[str] = []

    for i in range(edges.size - 1):
        low, high = float(edges[i]), float(edges[i + 1])
        members = values[bin_indices == i]
        n_members = int(members.size)
        underpopulated = n_members < minimum_sample_size

        if underpopulated:
            warnings.append(
                f"bin [{low:.3g}, {high:.3g}) has {n_members} members, "
                f"below minimum_sample_size={minimum_sample_size}"
            )

        mean = float(np.mean(members)) if n_members >= 1 else float("nan")
        std = float(np.std(members, ddof=1)) if n_members >= 2 else float("nan")
        bins.append(
            ScalarBin(bin_low=low, bin_high=high, mean=mean, std=std, n_members=n_members, underpopulated=underpopulated)
        )

    return ScalarBinningResult(bins=bins, warnings=warnings)
