"""Pixel-level validation of paired public ACS/WFC FLT and FLC products.

The calculations in this module operate on calibrated archive observations.
They do not estimate the physical CTE correction accuracy because the
untrailed scene is unknown.  Instead they test archive-pair identity,
calibration metadata, data-quality masks, charge redistribution, and ERR-array
scaling.  Robust location statistics use a deterministic pixel grid so a full
ACS frame does not need a second large in-memory copy merely to compute a
median.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from astropy.io import fits


PAIR_KEYS = ("ROOTNAME", "PROPOSID", "DATE-OBS", "EXPTIME", "FILTER1", "FILTER2", "CCDGAIN")


@dataclass(frozen=True)
class ChipPairAudit:
    rootname: str
    chip: int
    valid_pixel_count: int
    dq_disagreement_fraction: float
    net_charge_change_electrons: float
    fractional_net_charge_change: float
    median_pixel_change_electrons: float
    mad_pixel_change_electrons: float
    correction_rms_over_flt_error: float
    median_flc_to_flt_error_ratio: float

    def to_dict(self) -> dict[str, int | float | str]:
        return asdict(self)


def _same_pair_metadata(flt_header: fits.Header, flc_header: fits.Header) -> None:
    mismatches = [key for key in PAIR_KEYS if flt_header.get(key) != flc_header.get(key)]
    if mismatches:
        raise ValueError(f"FLT/FLC identity metadata disagree for {mismatches}")
    if str(flt_header.get("PCTECORR", "")).upper() != "PERFORM":
        raise ValueError("FLT input must record PCTECORR=PERFORM")
    if str(flc_header.get("PCTECORR", "")).upper() != "COMPLETE":
        raise ValueError("FLC product must record PCTECORR=COMPLETE")


def audit_flt_flc_pair(
    flt_path: str | Path,
    flc_path: str | Path,
    *,
    sample_stride: int = 8,
) -> tuple[list[ChipPairAudit], dict[str, str | float | int]]:
    """Audit one archive FLT/FLC pair over both ACS/WFC detector chips.

    ``fractional_net_charge_change`` divides the signed FLT-to-FLC difference
    by the absolute FLT charge.  This is a numerical closure diagnostic, not a
    photometric calibration claim: CTE correction can move charge across chip
    boundaries and flagged pixels are intentionally retained.
    """
    if sample_stride < 1:
        raise ValueError("sample_stride must be positive")

    with fits.open(flt_path, memmap=True) as flt, fits.open(flc_path, memmap=True) as flc:
        _same_pair_metadata(flt[0].header, flc[0].header)
        rootname = str(flt[0].header["ROOTNAME"])
        metadata: dict[str, str | float | int] = {
            "rootname": rootname,
            "proposal_id": int(flt[0].header["PROPOSID"]),
            "date_obs": str(flt[0].header["DATE-OBS"]),
            "exptime_seconds": float(flt[0].header["EXPTIME"]),
            "cal_ver": str(flt[0].header.get("CAL_VER", "")),
            "pctetab": str(flt[0].header.get("PCTETAB", "")),
        }

        audits: list[ChipPairAudit] = []
        for extver in (1, 2):
            flt_sci = np.asarray(flt["SCI", extver].data, dtype=np.float64)
            flc_sci = np.asarray(flc["SCI", extver].data, dtype=np.float64)
            flt_err = np.asarray(flt["ERR", extver].data, dtype=np.float64)
            flc_err = np.asarray(flc["ERR", extver].data, dtype=np.float64)
            flt_dq = np.asarray(flt["DQ", extver].data)
            flc_dq = np.asarray(flc["DQ", extver].data)
            if not (
                flt_sci.shape
                == flc_sci.shape
                == flt_err.shape
                == flc_err.shape
                == flt_dq.shape
                == flc_dq.shape
            ):
                raise ValueError(f"SCI/ERR/DQ shapes disagree for EXTVER={extver}")

            valid = np.isfinite(flt_sci) & np.isfinite(flc_sci)
            valid_count = int(valid.sum())
            if valid_count == 0:
                raise ValueError(f"no finite paired science pixels for EXTVER={extver}")

            delta = flc_sci - flt_sci
            net_change = float(np.sum(delta[valid], dtype=np.float64))
            absolute_charge = float(np.sum(np.abs(flt_sci[valid]), dtype=np.float64))
            fractional_change = net_change / absolute_charge if absolute_charge > 0 else float("nan")

            sampled = delta[::sample_stride, ::sample_stride]
            sampled = sampled[np.isfinite(sampled)]
            median_delta = float(np.median(sampled))
            mad_delta = float(np.median(np.abs(sampled - median_delta)))

            error_valid = valid & np.isfinite(flt_err) & np.isfinite(flc_err) & (flt_err > 0)
            rms_ratio = float(
                np.sqrt(np.mean(np.square(delta[error_valid]), dtype=np.float64))
                / np.median(flt_err[error_valid])
            )
            error_ratio = flc_err[error_valid] / flt_err[error_valid]

            audits.append(
                ChipPairAudit(
                    rootname=rootname,
                    chip=int(flt["SCI", extver].header.get("CCDCHIP", extver)),
                    valid_pixel_count=valid_count,
                    dq_disagreement_fraction=float(np.mean(flt_dq != flc_dq)),
                    net_charge_change_electrons=net_change,
                    fractional_net_charge_change=float(fractional_change),
                    median_pixel_change_electrons=median_delta,
                    mad_pixel_change_electrons=mad_delta,
                    correction_rms_over_flt_error=rms_ratio,
                    median_flc_to_flt_error_ratio=float(np.median(error_ratio)),
                )
            )
    return audits, metadata

