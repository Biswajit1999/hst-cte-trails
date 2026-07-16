"""FITS ingestion for ACS/WFC FLT/FLC products.

Maps archive-specific FITS structure onto the logical fields documented in
data/INPUT_SCHEMA.md: product_id, science_array, uncertainty_array, dq_mask,
wcs_or_detector_geometry, exposure_metadata, calibration_reference_ids.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits

from hst_acs_two_axis_cte_audit.exceptions import DataSchemaError
from hst_acs_two_axis_cte_audit.geometry import AmpGeometry, infer_geometry

REQUIRED_EXTENSIONS = ("SCI", "ERR", "DQ")
_CALIBRATION_KEYWORDS = ("PCTETAB", "DARKFILE", "BIASFILE", "FLSHFILE", "CCDTAB")


@dataclass(frozen=True)
class ExposureProduct:
    product_id: str
    science_array: np.ndarray
    uncertainty_array: np.ndarray
    dq_mask: np.ndarray
    geometry: AmpGeometry
    exposure_metadata: dict[str, Any]
    calibration_reference_ids: dict[str, str]


def load_exposure(path: str | Path, extver: int = 1) -> ExposureProduct:
    """Load one chip extension (SCI/ERR/DQ triplet) of an ACS/WFC FLT/FLC file.

    Raises DataSchemaError for a missing file, missing required extensions,
    mismatched array shapes, or missing required header keywords, per
    docs/ERROR_HANDLING.md.
    """
    fits_path = Path(path)
    if not fits_path.is_file():
        raise DataSchemaError(f"FITS product not found: {fits_path}")

    with fits.open(fits_path) as hdul:
        extnames = {hdu.name for hdu in hdul}
        missing_ext = [ext for ext in REQUIRED_EXTENSIONS if ext not in extnames]
        if missing_ext:
            raise DataSchemaError(f"{fits_path.name} missing required extensions: {missing_ext}")

        try:
            sci_hdu = hdul["SCI", extver]
            err_hdu = hdul["ERR", extver]
            dq_hdu = hdul["DQ", extver]
        except KeyError as exc:
            raise DataSchemaError(
                f"{fits_path.name} missing SCI/ERR/DQ triplet for EXTVER={extver}"
            ) from exc

        primary_header = hdul[0].header
        sci_header = sci_hdu.header

        science = np.asarray(sci_hdu.data, dtype=float)
        uncertainty = np.asarray(err_hdu.data, dtype=float)
        dq = np.asarray(dq_hdu.data, dtype=int)

        if science.shape != uncertainty.shape or science.shape != dq.shape:
            raise DataSchemaError(
                f"{fits_path.name}: SCI/ERR/DQ array shapes disagree: "
                f"{science.shape} vs {uncertainty.shape} vs {dq.shape}"
            )

        merged_header = dict(primary_header)
        merged_header.update(dict(sci_header))
        geometry = infer_geometry(merged_header)

        if "EXPTIME" not in primary_header:
            raise DataSchemaError(f"{fits_path.name} missing required EXPTIME header keyword")

        exposure_metadata: dict[str, Any] = {
            "exptime": float(primary_header["EXPTIME"]),
            "ccdgain": float(primary_header.get("CCDGAIN", np.nan)),
            "instrument": str(primary_header.get("INSTRUME", "")),
            "detector": str(primary_header.get("DETECTOR", "")),
            "filter1": str(primary_header.get("FILTER1", "")),
            "filter2": str(primary_header.get("FILTER2", "")),
            "subarray": bool(primary_header.get("SUBARRAY", False)),
        }
        calibration_reference_ids = {
            key: str(primary_header[key]) for key in _CALIBRATION_KEYWORDS if key in primary_header
        }
        product_id = str(primary_header.get("ROOTNAME", fits_path.stem))

    return ExposureProduct(
        product_id=product_id,
        science_array=science,
        uncertainty_array=uncertainty,
        dq_mask=dq,
        geometry=geometry,
        exposure_metadata=exposure_metadata,
        calibration_reference_ids=calibration_reference_ids,
    )
