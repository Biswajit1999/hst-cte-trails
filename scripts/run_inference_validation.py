"""Generate synthetic CTE inference-validation evidence."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from hst_acs_two_axis_cte_audit.inference_validation import (  # noqa: E402
    coverage_experiment,
    model_misspecification_experiment,
    window_sensitivity_experiment,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output = root / "results"
    coverage = coverage_experiment()
    windows = window_sensitivity_experiment()
    misspecification = model_misspecification_experiment()
    payload = {
        "schema": "hst-cte-inference-validation/1",
        "data_class": "synthetic injection-recovery; no HST measurements",
        "coverage": coverage,
        "window_sensitivity": windows,
        "single_exponential_misspecification": misspecification,
    }
    (output / "inference_validation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for name, rows in (("window_sensitivity.csv", windows), ("model_misspecification.csv", misspecification)):
        with (output / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)
    for stop in sorted({row["stop_pixel"] for row in windows}):
        chosen = [row for row in windows if row["stop_pixel"] == stop]
        axes[0].plot(
            [row["start_pixel"] for row in chosen],
            [100 * row["median_length_bias_fraction"] for row in chosen],
            marker="o",
            label=f"stop={stop} px",
        )
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set(xlabel="First fitted pixel behind source", ylabel="Median length bias (%)", title="Fit-window sensitivity")
    axes[0].legend(fontsize=8)
    axes[1].plot(
        [row["slow_amplitude_fraction"] for row in misspecification],
        [100 * row["median_total_charge_bias_fraction"] for row in misspecification],
        marker="o",
        color="#8b1e3f",
    )
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set(xlabel="Injected slow/fast amplitude ratio", ylabel="Median total-charge bias (%)", title="Single-exponential misspecification")
    figure.suptitle("Synthetic estimator validation — not HST observational results", fontsize=11)
    figure.savefig(output / "inference_validation.png", dpi=170)
    plt.close(figure)
    print(json.dumps({"coverage": coverage, "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
