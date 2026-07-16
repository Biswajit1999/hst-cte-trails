from __future__ import annotations

import pytest

from hst_acs_two_axis_cte_audit.exceptions import DataSchemaError
from hst_acs_two_axis_cte_audit.geometry import infer_geometry


def _base_header(**overrides):
    header = {"NAXIS1": 100, "NAXIS2": 120, "CCDCHIP": 1, "CCDAMP": "C"}
    header.update(overrides)
    return header


def test_amp_c_reads_bottom_left():
    geom = infer_geometry(_base_header(CCDAMP="C", CCDCHIP=1))
    assert geom.readout_row == 0
    assert geom.readout_col == 0


def test_amp_d_reads_bottom_right():
    geom = infer_geometry(_base_header(CCDAMP="D", CCDCHIP=1))
    assert geom.readout_row == 0
    assert geom.readout_col == 99


def test_amp_a_reads_top_left():
    geom = infer_geometry(_base_header(CCDAMP="A", CCDCHIP=2))
    assert geom.readout_row == 119
    assert geom.readout_col == 0


def test_amp_b_reads_top_right():
    geom = infer_geometry(_base_header(CCDAMP="B", CCDCHIP=2))
    assert geom.readout_row == 119
    assert geom.readout_col == 99


def test_quad_readout_selects_amp_for_chip():
    chip1 = infer_geometry(_base_header(CCDAMP="ABCD", CCDCHIP=1))
    chip2 = infer_geometry(_base_header(CCDAMP="ABCD", CCDCHIP=2))
    assert chip1.readout_row == 0  # chip 1 -> C/D pair -> row 0
    assert chip2.readout_row == 119  # chip 2 -> A/B pair -> row NAXIS2-1


def test_parallel_transfer_distance_matches_direction():
    geom = infer_geometry(_base_header(CCDAMP="C", CCDCHIP=1))
    assert geom.parallel_direction() == 1
    assert geom.parallel_transfer_distance(0) == 0
    assert geom.parallel_transfer_distance(50) == 50


def test_missing_required_keyword_raises_data_schema_error():
    header = _base_header()
    del header["CCDAMP"]
    with pytest.raises(DataSchemaError):
        infer_geometry(header)


def test_unrecognised_amp_letter_raises_data_schema_error():
    with pytest.raises(DataSchemaError):
        infer_geometry(_base_header(CCDAMP="Z"))


def test_non_integer_naxis_raises_data_schema_error():
    with pytest.raises(DataSchemaError):
        infer_geometry(_base_header(NAXIS1="not-a-number"))


def test_negative_naxis_raises_data_schema_error():
    with pytest.raises(DataSchemaError):
        infer_geometry(_base_header(NAXIS1=-10))
