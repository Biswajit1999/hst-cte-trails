"""Dependence-aware summaries for the bounded repeated-exposure audit."""
from __future__ import annotations

from collections import defaultdict

import numpy as np


def coordinate_cluster_medians(
    rows: list[dict[str, float | str]], tolerance_pixels: float = 0.75
) -> list[float]:
    """Collapse repeated measurements of the same detector source by position.

    The three exposures are aligned closely enough that a small detector-pixel
    radius identifies repeat measurements.  Clustering is deliberately greedy
    and deterministic (input order, then nearest eligible centroid).
    """
    if tolerance_pixels <= 0:
        raise ValueError("tolerance_pixels must be positive")
    clusters: list[list[dict[str, float | str]]] = []
    for row in rows:
        x, y = float(row["x"]), float(row["y"])
        candidates: list[tuple[float, int]] = []
        for index, cluster in enumerate(clusters):
            cx = float(np.mean([float(item["x"]) for item in cluster]))
            cy = float(np.mean([float(item["y"]) for item in cluster]))
            distance = float(np.hypot(x - cx, y - cy))
            if distance <= tolerance_pixels:
                candidates.append((distance, index))
        if candidates:
            clusters[min(candidates)[1]].append(row)
        else:
            clusters.append([row])
    return [
        float(np.median([float(item["suppression_fraction"]) for item in cluster]))
        for cluster in clusters
    ]


def bootstrap_median_interval(
    values: list[float], *, n_resamples: int, seed: int, confidence_level: float
) -> tuple[float, float, float]:
    if len(values) < 2:
        raise ValueError("at least two values are required")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be in (0, 1)")
    array = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    draws = np.median(
        array[rng.integers(0, array.size, size=(n_resamples, array.size))], axis=1
    )
    alpha = 1 - confidence_level
    low, high = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(np.median(array)), float(low), float(high)


def grouped_and_leave_one_out_medians(
    rows: list[dict[str, float | str]],
) -> tuple[dict[str, float], dict[str, float]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["rootname"])].append(float(row["suppression_fraction"]))
    group_medians = {key: float(np.median(values)) for key, values in sorted(grouped.items())}
    leave_one_out = {}
    for omitted in sorted(grouped):
        retained = [value for key, values in grouped.items() if key != omitted for value in values]
        leave_one_out[omitted] = float(np.median(retained))
    return group_medians, leave_one_out
