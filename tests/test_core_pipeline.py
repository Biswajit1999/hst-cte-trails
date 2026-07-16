from __future__ import annotations

import pytest

from hst_acs_two_axis_cte_audit.config import load_config
from hst_acs_two_axis_cte_audit.core import pair_flt_flc, run_pipeline
from hst_acs_two_axis_cte_audit.exceptions import InsufficientDataError
from conftest import SyntheticSource, SyntheticTrailSpec, build_synthetic_acs_hdulist


def test_pair_flt_flc_matches_by_rootname(tmp_path):
    rows = [{"product_id": "abc123_flt"}, {"product_id": "abc123_flc"}, {"product_id": "def456_flt"}]
    pairs = pair_flt_flc(rows, tmp_path)
    assert len(pairs) == 1
    assert pairs[0].rootname == "abc123"


def test_pair_flt_flc_raises_when_no_complete_pairs(tmp_path):
    rows = [{"product_id": "abc123_flt"}]
    with pytest.raises(InsufficientDataError):
        pair_flt_flc(rows, tmp_path)


def test_run_pipeline_end_to_end_on_synthetic_pairs(tmp_path):
    config = load_config("config/analysis.yml")
    manifest_rows = []
    sources = [
        (SyntheticSource(50, 90, 20000.0), SyntheticTrailSpec(0.05, 6.0), SyntheticTrailSpec(0.01, 6.0)),
        (SyntheticSource(30, 60, 15000.0), SyntheticTrailSpec(0.04, 5.0), SyntheticTrailSpec(0.008, 5.0)),
    ]
    for i, (source, flt_spec, flc_spec) in enumerate(sources):
        flt = build_synthetic_acs_hdulist(
            seed=20260713 + i, sources=(source,), parallel_trail=flt_spec, serial_trail=None, inject_hot_pixels=3
        )
        flc = build_synthetic_acs_hdulist(
            seed=20260713 + i, sources=(source,), parallel_trail=flc_spec, serial_trail=None, inject_hot_pixels=3
        )
        root = f"synthetic{i}"
        flt.writeto(tmp_path / f"{root}_flt.fits")
        flc.writeto(tmp_path / f"{root}_flc.fits")
        manifest_rows.append({"product_id": f"{root}_flt"})
        manifest_rows.append({"product_id": f"{root}_flc"})

    result = run_pipeline(manifest_rows, tmp_path, config, brightest_sources=5)

    assert len(result.measurements) == 2
    for measurement in result.measurements:
        assert 0.0 <= measurement.suppression.suppression_fraction <= 1.0
    assert result.hot_pixel_sample_size == 6
    assert any("minimum_sample_size" in w for w in result.warnings)


def test_run_pipeline_raises_on_empty_manifest(tmp_path):
    config = load_config("config/analysis.yml")
    with pytest.raises(InsufficientDataError):
        run_pipeline([], tmp_path, config)
