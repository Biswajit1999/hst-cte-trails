from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits

from hst_acs_two_axis_cte_audit.exceptions import DataSchemaError
from hst_acs_two_axis_cte_audit.fits_io import load_exposure
from conftest import SyntheticSource, build_synthetic_acs_hdulist


def test_load_exposure_reads_synthetic_fixture(tmp_path):
    hdul = build_synthetic_acs_hdulist(sources=(SyntheticSource(50, 90, 5000.0),))
    path = tmp_path / "synthetic.fits"
    hdul.writeto(path)

    product = load_exposure(path)

    assert product.science_array.shape == (120, 100)
    assert product.geometry.ccdamp == "C"
    assert product.exposure_metadata["exptime"] == 460.0
    assert product.exposure_metadata["instrument"] == "ACS"


def test_load_exposure_missing_file_raises():
    with pytest.raises(DataSchemaError):
        load_exposure("does_not_exist.fits")


def test_load_exposure_missing_extension_raises(tmp_path):
    primary = fits.PrimaryHDU(header=fits.Header({"EXPTIME": 100.0}))
    sci = fits.ImageHDU(data=np.zeros((10, 10)), name="SCI")
    sci.header["CCDCHIP"] = 1
    sci.header["CCDAMP"] = "C"
    hdul = fits.HDUList([primary, sci])  # missing ERR/DQ
    path = tmp_path / "incomplete.fits"
    hdul.writeto(path)

    with pytest.raises(DataSchemaError):
        load_exposure(path)


def test_load_exposure_mismatched_shapes_raises(tmp_path):
    primary = fits.PrimaryHDU(header=fits.Header({"EXPTIME": 100.0}))
    sci_header = fits.Header({"CCDCHIP": 1, "CCDAMP": "C"})
    sci = fits.ImageHDU(data=np.zeros((10, 10)), header=sci_header, name="SCI")
    err = fits.ImageHDU(data=np.ones((10, 10)), header=sci_header.copy(), name="ERR")
    dq = fits.ImageHDU(data=np.zeros((5, 5), dtype=np.int16), header=sci_header.copy(), name="DQ")
    hdul = fits.HDUList([primary, sci, err, dq])
    path = tmp_path / "mismatched.fits"
    hdul.writeto(path)

    with pytest.raises(DataSchemaError):
        load_exposure(path)


def test_load_exposure_missing_exptime_raises(tmp_path):
    primary = fits.PrimaryHDU()  # no EXPTIME
    sci_header = fits.Header({"CCDCHIP": 1, "CCDAMP": "C"})
    sci = fits.ImageHDU(data=np.zeros((10, 10)), header=sci_header, name="SCI")
    err = fits.ImageHDU(data=np.ones((10, 10)), header=sci_header.copy(), name="ERR")
    dq = fits.ImageHDU(data=np.zeros((10, 10), dtype=np.int16), header=sci_header.copy(), name="DQ")
    hdul = fits.HDUList([primary, sci, err, dq])
    path = tmp_path / "no_exptime.fits"
    hdul.writeto(path)

    with pytest.raises(DataSchemaError):
        load_exposure(path)
