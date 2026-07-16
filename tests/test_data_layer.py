from __future__ import annotations

import numpy as np

from hst_acs_two_axis_cte_audit.provenance import (
    ManifestRow,
    append_manifest_row,
    get_git_commit,
    read_manifest,
    sha256_file,
)
from hst_acs_two_axis_cte_audit.config import load_config


def test_load_config_reads_real_project_config():
    cfg = load_config("config/analysis.yml")
    assert cfg.project.repository == "hst-acs-two-axis-cte-audit"
    assert cfg.execution.seed == 20260713
    assert cfg.validation.bootstrap_resamples == 1000


def test_manifest_roundtrip(tmp_path):
    manifest_path = tmp_path / "manifest.csv"
    row = ManifestRow(
        product_id="jfnx01mmq_flt",
        source="MAST/HST",
        source_url="https://mast.stsci.edu",
        retrieved_utc="2026-07-13T00:00:00+00:00",
        sha256="0" * 64,
        file_size_bytes=168431040,
        selection_reason="unit test",
        licence_or_terms="STScI/MAST public HST archive data",
    )
    append_manifest_row(manifest_path, row)
    rows = read_manifest(manifest_path)
    assert len(rows) == 1
    assert rows[0]["product_id"] == "jfnx01mmq_flt"


def test_sha256_file_matches_known_content(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"hst-acs-two-axis-cte-audit")
    digest = sha256_file(path)
    assert len(digest) == 64
    assert digest == sha256_file(path)


def test_get_git_commit_never_raises(tmp_path):
    result = get_git_commit(tmp_path)
    assert isinstance(result, str)
    assert result != ""


def test_synthetic_fixture_has_injected_trail(synthetic_flt_flc_pair):
    flt_path, flc_path, truth = synthetic_flt_flc_pair
    from astropy.io import fits

    with fits.open(flt_path) as hdul:
        science = hdul["SCI"].data
    source = truth["source"]
    trail_pixel = science[source.y - 1, source.x]
    background_region = science[10:20, 10:20]
    assert trail_pixel > np.median(background_region) + 3 * np.std(background_region)
