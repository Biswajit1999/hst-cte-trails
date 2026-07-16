"""Shared synthetic-data fixtures for tests.

The synthetic-data model itself lives in
`hst_acs_two_axis_cte_audit.synthetic` (shared with `scripts/make_figures.py
--demo`); this module only adds the pytest fixture layer on top.
"""
from __future__ import annotations

import pytest

from hst_acs_two_axis_cte_audit.synthetic import (
    SyntheticSource,
    SyntheticTrailSpec,
    build_synthetic_acs_hdulist,
)

__all__ = ["SyntheticSource", "SyntheticTrailSpec", "build_synthetic_acs_hdulist", "synthetic_flt_flc_pair"]


@pytest.fixture
def synthetic_flt_flc_pair(tmp_path):
    """A (flt_path, flc_path, truth) tuple with a known injected trail.

    The FLC version has the same source but a documented, weaker trail,
    modelling imperfect-but-real pixel-based CTE correction so FLT-vs-FLC
    comparison tests have a known-truth suppression ratio.
    """
    truth_source = SyntheticSource(50, 90, 6000.0)
    flt_parallel = SyntheticTrailSpec(0.02, 6.0)
    flc_parallel = SyntheticTrailSpec(0.004, 6.0)  # ~80% suppression, known truth

    flt = build_synthetic_acs_hdulist(
        sources=(truth_source,), parallel_trail=flt_parallel, serial_trail=None, inject_hot_pixels=3
    )
    flc = build_synthetic_acs_hdulist(
        sources=(truth_source,), parallel_trail=flc_parallel, serial_trail=None, inject_hot_pixels=3
    )

    flt_path = tmp_path / "synthetic_flt.fits"
    flc_path = tmp_path / "synthetic_flc.fits"
    flt.writeto(flt_path)
    flc.writeto(flc_path)

    truth = {
        "source": truth_source,
        "flt_amplitude_fraction": flt_parallel.amplitude_fraction,
        "flt_length_pixels": flt_parallel.length_pixels,
        "flc_amplitude_fraction": flc_parallel.amplitude_fraction,
        "flc_length_pixels": flc_parallel.length_pixels,
        "suppression_fraction": 1 - flc_parallel.amplitude_fraction / flt_parallel.amplitude_fraction,
    }
    return flt_path, flc_path, truth
