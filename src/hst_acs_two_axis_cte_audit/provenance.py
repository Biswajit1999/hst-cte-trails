from __future__ import annotations

import csv
import subprocess
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from hst_acs_two_axis_cte_audit.exceptions import ProvenanceError

MANIFEST_COLUMNS = (
    "product_id",
    "source",
    "source_url",
    "retrieved_utc",
    "sha256",
    "file_size_bytes",
    "selection_reason",
    "licence_or_terms",
)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def sha256_config(config_path: str | Path) -> str:
    return sha256_file(config_path)


def get_git_commit(repo_dir: str | Path) -> str:
    """Return the short commit hash for repo_dir, or 'LOCAL_UNCOMMITTED' if unavailable.

    Read-only (`git rev-parse` never mutates repository state). Never raises: a
    missing git binary or an uninitialised repository are both expected states
    for this local-implementation workflow.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "LOCAL_UNCOMMITTED"
    if result.returncode != 0:
        return "LOCAL_UNCOMMITTED"
    return result.stdout.strip() or "LOCAL_UNCOMMITTED"


@dataclass(frozen=True)
class ManifestRow:
    product_id: str
    source: str
    source_url: str
    retrieved_utc: str
    sha256: str
    file_size_bytes: int
    selection_reason: str
    licence_or_terms: str


def append_manifest_row(manifest_path: str | Path, row: ManifestRow) -> None:
    path = Path(manifest_path)
    row_dict = asdict(row)
    missing = [c for c in MANIFEST_COLUMNS if c not in row_dict]
    if missing:
        raise ProvenanceError(f"manifest row missing required columns: {missing}")

    file_exists = path.is_file() and path.stat().st_size > 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(MANIFEST_COLUMNS))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_dict)


def read_manifest(manifest_path: str | Path) -> list[dict[str, str]]:
    path = Path(manifest_path)
    if not path.is_file():
        raise ProvenanceError(f"manifest file not found: {path}")
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    for row in rows:
        missing = [c for c in MANIFEST_COLUMNS if c not in row]
        if missing:
            raise ProvenanceError(f"manifest row missing required columns: {missing}")
    return rows


def verify_manifest_files(rows: list[dict[str, str]], raw_dir: str | Path) -> list[dict[str, object]]:
    """Verify every manifest product against its committed size and SHA-256.

    MAST calibrated products are mutable when the archive reprocesses an
    exposure.  A product id alone therefore does not identify the bytes used
    for an analysis; this check is a hard provenance gate, not an advisory.
    """
    base = Path(raw_dir)
    receipts: list[dict[str, object]] = []
    for row in rows:
        product_id = row["product_id"]
        path = base / f"{product_id}.fits"
        if not path.is_file():
            raise ProvenanceError(f"manifest product is missing: {path}")
        actual_size = path.stat().st_size
        expected_size = int(row["file_size_bytes"])
        if actual_size != expected_size:
            raise ProvenanceError(
                f"{product_id}: size {actual_size} does not match manifest {expected_size}"
            )
        actual_sha256 = sha256_file(path)
        expected_sha256 = row["sha256"].lower()
        if actual_sha256 != expected_sha256:
            raise ProvenanceError(
                f"{product_id}: SHA-256 {actual_sha256} does not match manifest {expected_sha256}"
            )
        receipts.append(
            {
                "product_id": product_id,
                "file_size_bytes": actual_size,
                "sha256": actual_sha256,
                "verified": True,
            }
        )
    return receipts


__all__ = [
    "MANIFEST_COLUMNS",
    "ManifestRow",
    "append_manifest_row",
    "read_manifest",
    "get_git_commit",
    "sha256_bytes",
    "sha256_config",
    "sha256_file",
    "verify_manifest_files",
]
