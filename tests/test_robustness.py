from __future__ import annotations

import pytest

from hst_acs_two_axis_cte_audit.robustness import (
    bootstrap_median_interval,
    coordinate_cluster_medians,
    grouped_and_leave_one_out_medians,
)


def test_coordinate_cluster_medians_collapse_repeated_sources():
    rows = [
        {"rootname": "a", "x": 10.0, "y": 20.0, "suppression_fraction": 0.7},
        {"rootname": "b", "x": 10.2, "y": 20.1, "suppression_fraction": 0.9},
        {"rootname": "a", "x": 40.0, "y": 50.0, "suppression_fraction": 0.2},
    ]
    assert coordinate_cluster_medians(rows) == [0.8, 0.2]


def test_grouped_and_leave_one_out_medians():
    rows = [
        {"rootname": "a", "suppression_fraction": 0.2},
        {"rootname": "a", "suppression_fraction": 0.4},
        {"rootname": "b", "suppression_fraction": 0.8},
    ]
    grouped, leave_one = grouped_and_leave_one_out_medians(rows)
    assert grouped == pytest.approx({"a": 0.3, "b": 0.8})
    assert leave_one == pytest.approx({"a": 0.8, "b": 0.3})


def test_bootstrap_median_is_seeded_and_ordered():
    first = bootstrap_median_interval([0.2, 0.4, 0.8], n_resamples=500, seed=7, confidence_level=0.95)
    second = bootstrap_median_interval([0.2, 0.4, 0.8], n_resamples=500, seed=7, confidence_level=0.95)
    assert first == second
    assert first[1] <= first[0] <= first[2]
