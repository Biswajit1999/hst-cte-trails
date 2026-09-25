"""Build dependence- and archive-refresh-aware evidence from real-data outputs."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt

from hst_acs_two_axis_cte_audit.robustness import (
    bootstrap_median_interval,
    coordinate_cluster_medians,
    grouped_and_leave_one_out_medians,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"


def main() -> None:
    rows = list(csv.DictReader((RESULTS / "measurements.csv").open(encoding="utf-8")))
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    baseline = json.loads((ROOT / "data" / "archive-refresh-baseline.json").read_text(encoding="utf-8"))
    cluster_values = coordinate_cluster_medians(rows)
    median, low, high = bootstrap_median_interval(
        cluster_values, n_resamples=10_000, seed=20260925, confidence_level=0.95
    )
    exposure_medians, leave_one_out = grouped_and_leave_one_out_medians(rows)
    current_metrics = {item["name"]: item for item in summary["metrics"]}
    current_suppression = current_metrics["median_suppression_fraction"]["estimate"]
    current_hot_pixel = current_metrics["hot_pixel_mean_excess"]["estimate"]

    evidence = {
        "scope": "Three consecutive exposures of one field; source-coordinate clusters are the resampling units.",
        "measurement_count": len(rows),
        "coordinate_cluster_count": len(cluster_values),
        "coordinate_tolerance_pixels": 0.75,
        "cluster_median_suppression": median,
        "cluster_bootstrap_95_interval": [low, high],
        "cluster_bootstrap_resamples": 10_000,
        "exposure_medians": exposure_medians,
        "leave_one_exposure_out_medians": leave_one_out,
        "archive_refresh": {
            "baseline_commit": baseline["baseline_commit"],
            "baseline_product_date": baseline["product_date"],
            "current_product_date": "2026-08-05",
            "baseline_median_suppression": baseline["median_suppression_fraction"],
            "current_median_suppression": current_suppression,
            "baseline_hot_pixel_mean_excess": baseline["hot_pixel_mean_excess"],
            "current_hot_pixel_mean_excess": current_hot_pixel,
            "all_six_sha256_changed": True,
        },
        "claim_boundary": (
            "Intervals describe estimator stability in this one-field, three-exposure sample. "
            "They are not a population-level calibration-accuracy interval."
        ),
    }
    (RESULTS / "robustness.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    design_rows = []
    for name, value in exposure_medians.items():
        design_rows.append({"design": "single_exposure", "omitted": "", "rootname": name, "median": value})
    for name, value in leave_one_out.items():
        design_rows.append({"design": "leave_one_exposure_out", "omitted": name, "rootname": "", "median": value})
    with (RESULTS / "robustness_designs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("design", "omitted", "rootname", "median"))
        writer.writeheader()
        writer.writerows(design_rows)

    FIGURES.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.6), constrained_layout=True)
    axes[0].bar(["July manifest\n(old bytes)", "September audit\n(current bytes)"], [baseline["median_suppression_fraction"], current_suppression], color=["#94a3b8", "#0f766e"])
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Median fitted suppression fraction")
    axes[0].set_title("Archive refresh changes the headline")
    axes[0].text(0, baseline["median_suppression_fraction"] + 0.025, f'{baseline["median_suppression_fraction"]:.3f}', ha="center")
    axes[0].text(1, current_suppression + 0.025, f"{current_suppression:.3f}", ha="center")

    labels = list(exposure_medians) + [f"omit {name[-3:]}" for name in leave_one_out]
    values = list(exposure_medians.values()) + list(leave_one_out.values())
    colors = ["#2563eb"] * len(exposure_medians) + ["#d97706"] * len(leave_one_out)
    axes[1].scatter(range(len(values)), values, c=colors, s=70, zorder=3)
    axes[1].axhspan(low, high, color="#0f766e", alpha=0.14, label="cluster bootstrap 95% interval")
    axes[1].axhline(median, color="#0f766e", linewidth=1.6, label="cluster median")
    axes[1].set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    axes[1].set_ylim(min(values + [low]) - 0.1, max(values + [high]) + 0.1)
    axes[1].set_title("Exposure and deletion sensitivity")
    axes[1].set_ylabel("Median fitted suppression fraction")
    axes[1].legend(frameon=False, fontsize=8)
    figure.suptitle("HST ACS/WFC parallel-trail estimator robustness", fontsize=14, fontweight="bold")
    figure.savefig(FIGURES / "fig07_archive_robustness.png", dpi=180)
    figure.savefig(FIGURES / "fig07_archive_robustness.svg")
    plt.close(figure)
    print(f"Wrote robustness evidence for {len(rows)} measurements in {len(cluster_values)} coordinate clusters")


if __name__ == "__main__":
    main()
