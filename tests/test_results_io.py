from __future__ import annotations

import json

import pytest

from hst_acs_two_axis_cte_audit.exceptions import DataSchemaError
from hst_acs_two_axis_cte_audit.results_io import Metric, validate_summary, write_summary


def test_write_summary_roundtrip(tmp_path):
    metrics = [Metric(name="suppression_fraction", estimate=0.8, units="dimensionless", sample_size=10, uncertainty_low=0.7, uncertainty_high=0.9)]
    path = tmp_path / "summary.json"
    payload = write_summary(path, "test-project", "synthetic_smoke_test", metrics, {"git_commit": "abc"}, [])

    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == payload
    assert loaded["metrics"][0]["name"] == "suppression_fraction"


def test_validate_summary_rejects_missing_top_key():
    with pytest.raises(DataSchemaError):
        validate_summary({"project": "x", "data_kind": "y", "metrics": [], "warnings": []})


def test_validate_summary_rejects_metric_missing_required_field():
    payload = {
        "project": "x",
        "data_kind": "y",
        "metrics": [{"name": "m", "estimate": 1.0}],
        "provenance": {},
        "warnings": [],
    }
    with pytest.raises(DataSchemaError):
        validate_summary(payload)
