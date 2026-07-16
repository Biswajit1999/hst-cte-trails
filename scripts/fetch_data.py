"""Deterministic, provenance-recording fetch of real public HST ACS/WFC data.

Queries MAST directly (no fabricated metadata). Selects a small, deterministic
sample of FLT/FLC exposure pairs from a public ACS/WFC program, downloads them
to data/raw/ (git-ignored), verifies checksums, and appends rows to
data/manifest.csv and data/provenance.yml.

This script performs real network downloads (~170 MB per FITS file) and must
only be invoked with explicit user authorization for the session, per the
project's data-acquisition rules in docs/DATASET_PLAN.md.
"""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

from hst_acs_two_axis_cte_audit.exceptions import ArchiveAccessError
from hst_acs_two_axis_cte_audit.logging_utils import get_logger
from hst_acs_two_axis_cte_audit.provenance import ManifestRow, append_manifest_row, sha256_file

LOGGER = get_logger(__name__)

PROPOSAL_ID = "18004"
INSTRUMENT = "ACS/WFC"
FILTER_NAME = "F606W"
LICENCE_TERMS = (
    "STScI/MAST public HST archive data (dataRights=PUBLIC), no proprietary period; "
    "standard STScI archive usage terms apply, https://archive.stsci.edu/copyright.html"
)
SOURCE_URL = "https://mast.stsci.edu"


def _select_observations(n_exposures: int):
    """Query MAST for the deterministic exposure sample.

    Raises ArchiveAccessError if the query fails, returns no rows, or any
    selected observation is not confirmed PUBLIC.
    """
    try:
        from astroquery.mast import Observations
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ArchiveAccessError(
            "astroquery is not installed in this environment"
        ) from exc

    try:
        obs = Observations.query_criteria(
            obs_collection="HST",
            instrument_name=INSTRUMENT,
            proposal_id=[PROPOSAL_ID],
            dataproduct_type="image",
            calib_level=[2],
            filters=FILTER_NAME,
        )
    except Exception as exc:  # noqa: BLE001 - any archive/network failure is fatal here
        raise ArchiveAccessError(f"MAST query failed: {exc}") from exc

    if len(obs) == 0:
        raise ArchiveAccessError(
            f"MAST query for proposal {PROPOSAL_ID} returned zero observations"
        )

    obs.sort("obs_id")
    selected = obs[:n_exposures]

    for row in selected:
        if str(row["dataRights"]) != "PUBLIC":
            raise ArchiveAccessError(
                f"observation {row['obs_id']} is not PUBLIC (dataRights="
                f"{row['dataRights']!r}); refusing to download"
            )
    return selected, obs


def _download_flt_flc(observations, out_dir: Path):
    """Download exposure-level FLT/FLC products and flatten them into out_dir.

    astroquery's downloader nests files under
    out_dir/mastDownload/HST/<obs_id>/<filename>.fits; this pipeline's
    manifest/pairing logic (hst_acs_two_axis_cte_audit.core.pair_flt_flc)
    expects a flat out_dir/<product_id>.fits layout, so each file is moved
    immediately after download. Only exposure-level products (filenames not
    prefixed "hst_", e.g. "jfnx01mhq_flt.fits") are requested — MAST also
    lists an association-level combined FLC copy per exposure
    ("hst_<prop>_..._flc.fits") with no FLT counterpart, which would be
    downloaded but never used by FLT/FLC pairing, wasting bandwidth.
    """
    from astroquery.mast import Observations

    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for row in observations:
        try:
            products = Observations.get_product_list(observations[observations["obs_id"] == row["obs_id"]])
        except Exception as exc:  # noqa: BLE001
            raise ArchiveAccessError(f"failed to list products for {row['obs_id']}: {exc}") from exc

        subset = products[
            ((products["productSubGroupDescription"] == "FLT") | (products["productSubGroupDescription"] == "FLC"))
            & ([not str(name).startswith("hst_") for name in products["productFilename"]])
        ]
        if len(subset) == 0:
            raise ArchiveAccessError(f"no exposure-level FLT/FLC products found for {row['obs_id']}")

        download_manifest = Observations.download_products(subset, download_dir=str(out_dir))
        for local_path_str in download_manifest["Local Path"]:
            nested_path = Path(local_path_str)
            flat_path = out_dir / nested_path.name
            if nested_path != flat_path:
                shutil.move(str(nested_path), str(flat_path))
            downloaded.append(flat_path)

    mast_download_dir = out_dir / "mastDownload"
    if mast_download_dir.is_dir():
        shutil.rmtree(mast_download_dir, ignore_errors=True)

    return downloaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n-exposures",
        type=int,
        default=3,
        help="Number of exposures (each yielding one FLT + one FLC file) to fetch deterministically.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory to store downloaded FITS files (git-ignored).",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifest.csv"),
        help="Manifest CSV to append provenance rows to.",
    )
    parser.add_argument(
        "--i-have-authorization",
        action="store_true",
        help=(
            "Required flag confirming the operator has explicitly authorized this "
            "real network download in the current session."
        ),
    )
    args = parser.parse_args()

    if not args.i_have_authorization:
        raise SystemExit(
            "Refusing to download real archive data without --i-have-authorization. "
            "This flag exists so the download only runs after the operator has "
            "explicitly confirmed it in the current session (see docs/DATASET_PLAN.md)."
        )

    selected, _all_obs = _select_observations(args.n_exposures)
    LOGGER.info("Selected %d observations from proposal %s", len(selected), PROPOSAL_ID)

    downloaded = _download_flt_flc(selected, args.out_dir)
    retrieved_utc = datetime.now(timezone.utc).isoformat()

    for local_path in downloaded:
        if not local_path.is_file():
            raise ArchiveAccessError(f"expected downloaded file missing: {local_path}")
        digest = sha256_file(local_path)
        size = local_path.stat().st_size
        row = ManifestRow(
            product_id=local_path.stem,
            source="MAST/HST",
            source_url=SOURCE_URL,
            retrieved_utc=retrieved_utc,
            sha256=digest,
            file_size_bytes=size,
            selection_reason=(
                f"deterministic first-{args.n_exposures} public ACS/WFC {FILTER_NAME} "
                f"FLT/FLC exposure sample from proposal {PROPOSAL_ID}, sorted by obs_id, "
                "for CTE trail suppression audit"
            ),
            licence_or_terms=LICENCE_TERMS,
        )
        append_manifest_row(args.manifest, row)
        LOGGER.info("Recorded manifest row for %s (%d bytes)", local_path.name, size)

    print(f"Downloaded and recorded {len(downloaded)} files under {args.out_dir}")


if __name__ == "__main__":
    main()
