from __future__ import annotations

import numpy as np
import pytest

from hst_acs_two_axis_cte_audit.exceptions import InsufficientDataError
from hst_acs_two_axis_cte_audit.stacking import bin_and_stack, bin_scalar_statistic, stack_profiles
from hst_acs_two_axis_cte_audit.trail_profiles import TrailProfile


def _profile(values, axis="parallel"):
    return TrailProfile(distances=np.arange(1.0, len(values) + 1), values=np.array(values), axis=axis)


def test_stack_profiles_averages_correctly():
    profiles = [_profile([10.0, 8.0, 6.0]), _profile([20.0, 16.0, 12.0])]
    stacked = stack_profiles(profiles)
    assert np.allclose(stacked.mean_values, [15.0, 12.0, 9.0])
    assert stacked.n_stacked == 2


def test_stack_profiles_rejects_empty_list():
    with pytest.raises(InsufficientDataError):
        stack_profiles([])


def test_stack_profiles_rejects_mixed_axes():
    with pytest.raises(InsufficientDataError):
        stack_profiles([_profile([1.0, 2.0], axis="parallel"), _profile([1.0, 2.0], axis="serial")])


def test_stack_profiles_rejects_mismatched_distance_grids():
    a = TrailProfile(distances=np.array([1.0, 2.0]), values=np.array([1.0, 2.0]), axis="parallel")
    b = TrailProfile(distances=np.array([1.0, 3.0]), values=np.array([1.0, 2.0]), axis="parallel")
    with pytest.raises(InsufficientDataError):
        stack_profiles([a, b])


def test_bin_and_stack_flags_underpopulated_bins():
    profiles = [_profile([1.0, 2.0]) for _ in range(3)]
    keys = np.array([1.0, 2.0, 3.0])
    result = bin_and_stack(keys, profiles, edges=np.array([0.0, 5.0]), minimum_sample_size=10)
    assert len(result.bins) == 1
    assert result.bins[0].n_members == 3
    assert result.bins[0].underpopulated is True
    assert len(result.warnings) == 1


def test_bin_scalar_statistic_computes_mean_per_bin():
    keys = np.array([1.0, 1.5, 5.0, 5.5])
    values = np.array([10.0, 12.0, 100.0, 104.0])
    result = bin_scalar_statistic(keys, values, edges=np.array([0.0, 3.0, 6.0]), minimum_sample_size=1)
    assert len(result.bins) == 2
    assert result.bins[0].mean == pytest.approx(11.0)
    assert result.bins[1].mean == pytest.approx(102.0)
    assert not result.bins[0].underpopulated


def test_bin_scalar_statistic_rejects_mismatched_shapes():
    with pytest.raises(InsufficientDataError):
        bin_scalar_statistic(np.array([1.0, 2.0]), np.array([1.0]), edges=np.array([0.0, 3.0]), minimum_sample_size=1)
