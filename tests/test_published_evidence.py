from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_published_evidence_is_traceable_and_internally_consistent() -> None:
    summary = _json(ROOT / "results" / "summary.json")
    robustness = _json(ROOT / "results" / "robustness.json")
    provenance = summary["provenance"]

    with (ROOT / "results" / "measurements.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        measurements = list(csv.DictReader(handle))

    assert summary["project"] == "HST ACS/WFC Parallel-Trail Estimator Audit"
    assert provenance["input_receipts_verified"] is True
    assert provenance["n_flt_flc_pairs"] == 3
    assert provenance["git_commit"] != "LOCAL_UNCOMMITTED"
    assert robustness["measurement_count"] == len(measurements) == 38
    assert robustness["coordinate_cluster_count"] <= robustness["measurement_count"]
    assert robustness["cluster_bootstrap_resamples"] == 10_000
    assert robustness["archive_refresh"]["all_six_sha256_changed"] is True


def test_manifest_has_six_exact_versioned_receipts() -> None:
    with (ROOT / "data" / "manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 6
    assert len({row["product_id"] for row in rows}) == 6
    assert len({row["source_url"] for row in rows}) == 6
    for row in rows:
        assert row["source_url"].endswith(f"{row['product_id']}.fits")
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        assert int(row["file_size_bytes"]) > 0


def test_web_bundle_matches_canonical_evidence() -> None:
    mirrored_files = (
        "summary.json",
        "warnings.json",
        "benchmarks.json",
        "measurements.csv",
        "robustness.json",
        "robustness_designs.csv",
    )
    for name in mirrored_files:
        assert (ROOT / "results" / name).read_bytes() == (
            ROOT / "web-react" / "public" / "results" / name
        ).read_bytes()

    assert (ROOT / "data" / "manifest.csv").read_bytes() == (
        ROOT / "web-react" / "public" / "manifest.csv"
    ).read_bytes()
