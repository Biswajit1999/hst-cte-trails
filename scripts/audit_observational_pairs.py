"""Audit the committed-manifest ACS/WFC FLT/FLC observations at pixel level."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

from hst_acs_two_axis_cte_audit.core import pair_flt_flc
from hst_acs_two_axis_cte_audit.observational_pair_audit import audit_flt_flc_pair
from hst_acs_two_axis_cte_audit.provenance import read_manifest, verify_manifest_files

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


def main() -> None:
    rows = read_manifest(ROOT / "data" / "manifest.csv")
    verify_manifest_files(rows, ROOT / "data" / "raw")
    pairs = pair_flt_flc(rows, ROOT / "data" / "raw")

    audits: list[dict] = []
    metadata: list[dict] = []
    for pair in pairs:
        pair_audits, pair_metadata = audit_flt_flc_pair(pair.flt_path, pair.flc_path)
        audits.extend(item.to_dict() for item in pair_audits)
        metadata.append(pair_metadata)

    RESULTS.mkdir(exist_ok=True)
    FIGURES.mkdir(exist_ok=True)
    csv_path = RESULTS / "observational_pair_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audits[0]))
        writer.writeheader()
        writer.writerows(audits)

    summary = {
        "data_kind": "real public HST ACS/WFC calibrated archive observations",
        "archive_pairs": len(pairs),
        "chip_comparisons": len(audits),
        "metadata": metadata,
        "calibration_metadata_consistent": len({(m["cal_ver"], m["pctetab"]) for m in metadata}) == 1,
        "maximum_absolute_fractional_net_charge_change": max(
            abs(row["fractional_net_charge_change"]) for row in audits
        ),
        "maximum_dq_disagreement_fraction": max(row["dq_disagreement_fraction"] for row in audits),
        "claim_boundary": (
            "These are FLT/FLC product-consistency diagnostics. The latent untrailed sky is unknown, "
            "so they do not measure absolute CTE-correction accuracy."
        ),
    }
    (RESULTS / "observational_pair_audit.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    labels = [f"{row['rootname'][-3:]} / chip {row['chip']}" for row in audits]
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    axes[0].bar(labels, [100 * row["fractional_net_charge_change"] for row in audits], color="#0f766e")
    axes[0].axhline(0, color="#334155", linewidth=0.8)
    axes[0].set_ylabel("Net FLT→FLC change / |FLT charge| (%)")
    axes[0].set_title("Whole-chip numerical charge closure")
    axes[0].tick_params(axis="x", rotation=40)

    error_ratio_change_percent = [
        100 * (row["median_flc_to_flt_error_ratio"] - 1) for row in audits
    ]
    axes[1].scatter(
        error_ratio_change_percent,
        [row["correction_rms_over_flt_error"] for row in audits],
        c=[row["chip"] for row in audits],
        cmap="viridis",
        s=75,
    )
    for index, (label, row, ratio_change) in enumerate(
        zip(labels, audits, error_ratio_change_percent, strict=True)
    ):
        axes[1].annotate(
            label,
            (ratio_change, row["correction_rms_over_flt_error"]),
            xytext=(5, 5 if index % 2 == 0 else -10),
            textcoords="offset points",
            fontsize=7,
        )
    axes[1].set_xlabel("Median FLC / FLT ERR change (%)")
    axes[1].set_ylabel("RMS correction / median FLT ERR")
    axes[1].set_title("Correction scale relative to uncertainty arrays")
    figure.suptitle("Observed ACS/WFC FLT–FLC pair audit", fontweight="bold")
    figure.savefig(FIGURES / "fig08_observational_pair_audit.png", dpi=180)
    plt.close(figure)
    print(f"Audited {len(pairs)} verified archive pairs across {len(audits)} detector chips")


if __name__ == "__main__":
    main()

