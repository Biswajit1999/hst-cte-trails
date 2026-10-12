from pathlib import Path

import numpy as np
import pytest
from astropy.io import fits

from hst_acs_two_axis_cte_audit.observational_pair_audit import audit_flt_flc_pair


def _write_product(path: Path, *, corrected: bool, proposal_id: int = 18004) -> None:
    primary = fits.PrimaryHDU()
    primary.header.update(
        ROOTNAME="testroot",
        PROPOSID=proposal_id,
        EXPTIME=100.0,
        FILTER1="F606W",
        FILTER2="CLEAR2L",
        CCDGAIN=2.0,
        PCTECORR="COMPLETE" if corrected else "PERFORM",
        CAL_VER="test",
        PCTETAB="test_cte.fits",
    )
    primary.header["DATE-OBS"] = "2026-07-02"
    hdus = [primary]
    for extver, chip in ((1, 2), (2, 1)):
        sci = np.full((8, 10), 10.0 + (0.5 if corrected else 0.0), dtype=np.float32)
        err = np.full_like(sci, 2.0 if corrected else 1.0)
        dq = np.zeros_like(sci, dtype=np.int16)
        hdus.extend(
            [
                fits.ImageHDU(sci, name="SCI", header=fits.Header({"EXTVER": extver, "CCDCHIP": chip})),
                fits.ImageHDU(err, name="ERR", header=fits.Header({"EXTVER": extver})),
                fits.ImageHDU(dq, name="DQ", header=fits.Header({"EXTVER": extver})),
            ]
        )
    fits.HDUList(hdus).writeto(path)


def test_pair_audit_recovers_known_pixel_change(tmp_path: Path) -> None:
    flt = tmp_path / "test_flt.fits"
    flc = tmp_path / "test_flc.fits"
    _write_product(flt, corrected=False)
    _write_product(flc, corrected=True)

    audits, metadata = audit_flt_flc_pair(flt, flc, sample_stride=2)

    assert len(audits) == 2
    assert metadata["proposal_id"] == 18004
    assert all(item.median_pixel_change_electrons == pytest.approx(0.5) for item in audits)
    assert all(item.fractional_net_charge_change == pytest.approx(0.05) for item in audits)
    assert all(item.median_flc_to_flt_error_ratio == pytest.approx(2.0) for item in audits)
    assert all(item.dq_disagreement_fraction == 0.0 for item in audits)


def test_pair_audit_rejects_identity_mismatch(tmp_path: Path) -> None:
    flt = tmp_path / "test_flt.fits"
    flc = tmp_path / "test_flc.fits"
    _write_product(flt, corrected=False)
    _write_product(flc, corrected=True, proposal_id=99)

    with pytest.raises(ValueError, match="identity metadata"):
        audit_flt_flc_pair(flt, flc)

