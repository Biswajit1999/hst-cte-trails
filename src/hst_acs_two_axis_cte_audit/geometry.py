"""Header-driven ACS/WFC readout geometry.

ASSUMPTION (documented, not independently re-derived from CALACS or flight
hardware drawings — see docs/ASSUMPTIONS_AND_LIMITATIONS.md): the
CCDAMP header keyword identifies which corner of the assembled SCI array is
adjacent to the readout amplifier for that chip/extension, following the
standard convention that amplifiers C/D read out at row 0 (bottom of the
array) and A/B read out at row NAXIS2-1 (top); C/A read out at column 0
(left) and D/B at column NAXIS1-1 (right). If a specific exposure's header
configuration does not match this convention, the sign of the inferred
transfer distance would be flipped; this is a stated limitation of a
first-release bounded audit, not a hardware-verified guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hst_acs_two_axis_cte_audit.exceptions import DataSchemaError

_ROW0_AMPS = {"C", "D"}
_COL0_AMPS = {"C", "A"}
_VALID_AMPS = {"A", "B", "C", "D"}


@dataclass(frozen=True)
class AmpGeometry:
    naxis1: int
    naxis2: int
    ccdchip: int
    ccdamp: str
    readout_row: int
    readout_col: int

    def parallel_transfer_distance(self, y: np.ndarray) -> np.ndarray:
        """Number of parallel shifts from row y to the readout register."""
        return np.abs(np.asarray(y, dtype=float) - self.readout_row)

    def serial_transfer_distance(self, x: np.ndarray) -> np.ndarray:
        """Number of serial shifts from column x to the readout register."""
        return np.abs(np.asarray(x, dtype=float) - self.readout_col)

    def parallel_direction(self) -> int:
        """+1 if distance increases with row index, else -1."""
        return 1 if self.readout_row == 0 else -1

    def serial_direction(self) -> int:
        """+1 if distance increases with column index, else -1."""
        return 1 if self.readout_col == 0 else -1


def _select_amp_letter(ccdamp: str, ccdchip: int) -> str:
    """Pick one amp letter to represent a (possibly multi-amp) readout.

    For quad-readout ('ABCD') full-frame exposures both amps sharing a chip
    read the same physical row (only the column split differs), so any
    single letter from the chip's amp pair yields the correct parallel
    geometry; ccdchip selects which pair (A/B for chip 2, C/D for chip 1) per
    the documented convention above.
    """
    letters = [c for c in ccdamp.upper() if c in _VALID_AMPS]
    if not letters:
        raise DataSchemaError(f"CCDAMP header value has no recognised amp letters: {ccdamp!r}")
    if len(letters) == 1:
        return letters[0]

    chip_pair = {2: ("A", "B"), 1: ("C", "D")}.get(ccdchip)
    if chip_pair is None:
        raise DataSchemaError(f"unsupported CCDCHIP value for multi-amp geometry: {ccdchip!r}")
    for letter in chip_pair:
        if letter in letters:
            return letter
    raise DataSchemaError(
        f"CCDAMP={ccdamp!r} does not contain either expected amp for CCDCHIP={ccdchip!r} "
        f"(expected one of {chip_pair})"
    )


def infer_geometry(header: dict) -> AmpGeometry:
    """Derive AmpGeometry from a FITS header-like mapping.

    Raises DataSchemaError if required keywords are missing or malformed —
    this is the documented failure test target for header-driven geometry.
    """
    required = ("NAXIS1", "NAXIS2", "CCDCHIP", "CCDAMP")
    missing = [key for key in required if key not in header]
    if missing:
        raise DataSchemaError(f"header is missing required geometry keywords: {missing}")

    try:
        naxis1 = int(header["NAXIS1"])
        naxis2 = int(header["NAXIS2"])
        ccdchip = int(header["CCDCHIP"])
    except (TypeError, ValueError) as exc:
        raise DataSchemaError(f"header geometry keywords are not valid integers: {exc}") from exc

    if naxis1 <= 0 or naxis2 <= 0:
        raise DataSchemaError(f"header NAXIS1/NAXIS2 must be positive, got {naxis1}x{naxis2}")

    ccdamp_raw = header["CCDAMP"]
    if not isinstance(ccdamp_raw, str) or not ccdamp_raw.strip():
        raise DataSchemaError(f"header CCDAMP must be a non-empty string, got {ccdamp_raw!r}")

    amp_letter = _select_amp_letter(ccdamp_raw, ccdchip)
    readout_row = 0 if amp_letter in _ROW0_AMPS else naxis2 - 1
    readout_col = 0 if amp_letter in _COL0_AMPS else naxis1 - 1

    return AmpGeometry(
        naxis1=naxis1,
        naxis2=naxis2,
        ccdchip=ccdchip,
        ccdamp=ccdamp_raw.strip().upper(),
        readout_row=readout_row,
        readout_col=readout_col,
    )
