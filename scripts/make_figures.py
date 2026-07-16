"""Generate the 6 required figures (docs/FIGURE_AND_UI_SPEC.md) as SVG + 300 dpi PNG,
each with a sidecar JSON recording git commit, config hash, sample size and units.

--demo builds figures from the synthetic, clearly-labelled data model in
`hst_acs_two_axis_cte_audit.synthetic` (never presented as a scientific
result). The real-data path reads `results/summary.json` plus the actual
FLT/FLC pairs and must only be run after `scripts/run_analysis.py` (real
mode) has produced validated results.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hst_acs_two_axis_cte_audit import __version__
from hst_acs_two_axis_cte_audit.config import load_config
from hst_acs_two_axis_cte_audit.core import pair_flt_flc, run_pipeline
from hst_acs_two_axis_cte_audit.exceptions import ConvergenceError, InsufficientDataError
from hst_acs_two_axis_cte_audit.fits_io import load_exposure
from hst_acs_two_axis_cte_audit.geometry import infer_geometry
from hst_acs_two_axis_cte_audit.plotting import plot_demo
from hst_acs_two_axis_cte_audit.provenance import get_git_commit, read_manifest, sha256_config
from hst_acs_two_axis_cte_audit.synthetic import SyntheticSource, SyntheticTrailSpec, build_synthetic_acs_hdulist
from hst_acs_two_axis_cte_audit.trail_profiles import (
    detect_sources,
    extract_parallel_trail,
    fit_exponential_trail,
    exponential_trail_model,
)


def _sidecar(path: Path, *, data_kind: str, sample_size: int, units: str, config_path: Path, extra: dict | None = None) -> None:
    payload = {
        "figure": path.stem,
        "data_kind": data_kind,
        "sample_size": sample_size,
        "units": units,
        "git_commit": get_git_commit(Path(__file__).resolve().parents[1]),
        "config_sha256": sha256_config(config_path) if config_path.is_file() else None,
        "package_version": __version__,
    }
    if extra:
        payload.update(extra)
    path.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _save(fig, out_dir: Path, name: str) -> Path:
    svg_path = out_dir / f"{name}.svg"
    png_path = out_dir / f"{name}.png"
    fig.savefig(svg_path)
    fig.savefig(png_path, dpi=300)
    plt.close(fig)
    return png_path


def make_demo_figures(out_dir: Path, config_path: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    data_kind = "synthetic_demo"

    source = SyntheticSource(50, 90, 20000.0)
    flt_spec = SyntheticTrailSpec(0.05, 6.0)
    flc_spec = SyntheticTrailSpec(0.01, 6.0)
    flt_hdul = build_synthetic_acs_hdulist(sources=(source,), parallel_trail=flt_spec, serial_trail=None, inject_hot_pixels=6)
    flc_hdul = build_synthetic_acs_hdulist(sources=(source,), parallel_trail=flc_spec, serial_trail=None, inject_hot_pixels=6)
    header = dict(flt_hdul[0].header) | dict(flt_hdul["SCI"].header)
    geometry = infer_geometry(header)

    # 1. detector geometry
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.add_patch(plt.Rectangle((0, 0), geometry.naxis1, geometry.naxis2, fill=False, edgecolor="black"))
    ax.plot(geometry.readout_col, geometry.readout_row, "rs", markersize=12, label="Readout amplifier (schematic)")
    ax.annotate("parallel transfer direction", xy=(geometry.naxis1 * 0.5, geometry.naxis2 * 0.5),
                xytext=(geometry.naxis1 * 0.5, geometry.naxis2 * 0.9),
                arrowprops=dict(arrowstyle="->"), ha="center")
    ax.set_xlim(-5, geometry.naxis1 + 5)
    ax.set_ylim(-5, geometry.naxis2 + 5)
    ax.set_xlabel("Column (pixels, serial axis)")
    ax.set_ylabel("Row (pixels, parallel axis)")
    ax.set_title(f"Detector geometry (header-derived; CCDAMP={geometry.ccdamp}, CCDCHIP={geometry.ccdchip})\nSYNTHETIC DEMO", fontsize=11)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    path = _save(fig, out_dir, "fig01_detector_geometry")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="pixels", config_path=config_path)

    # 2. example trails (image cutout around the source)
    y0, y1 = max(0, source.y - 25), min(geometry.naxis2, source.y + 5)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5), sharey=True)
    for ax, hdul, label in ((axes[0], flt_hdul, "FLT (uncorrected)"), (axes[1], flc_hdul, "FLC (CTE-corrected)")):
        cutout = hdul["SCI"].data[y0:y1, source.x - 15 : source.x + 15]
        im = ax.imshow(cutout, origin="lower", cmap="viridis", vmin=15, vmax=200)
        ax.set_title(label)
        ax.set_xlabel("Column offset (pixels)")
    axes[0].set_ylabel("Row offset (pixels)")
    fig.suptitle("Example parallel CTE trail behind a synthetic point source — SYNTHETIC DEMO")
    fig.colorbar(im, ax=axes, shrink=0.8, label="Counts (electrons)")
    path = _save(fig, out_dir, "fig02_example_trails")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="electrons", config_path=config_path)

    # 3. FLT vs FLC profiles
    flt_profile = extract_parallel_trail(flt_hdul["SCI"].data, geometry, source.x, source.y)
    flc_profile = extract_parallel_trail(flc_hdul["SCI"].data, geometry, source.x, source.y)
    flt_fit = fit_exponential_trail(flt_profile)
    flc_fit = fit_exponential_trail(flc_profile)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(flt_profile.distances, flt_profile.values, "o", label="FLT data", color="tab:orange")
    ax.plot(flt_profile.distances, exponential_trail_model(flt_profile.distances, flt_fit.amplitude, flt_fit.length, flt_fit.offset), "-", color="tab:orange", label="FLT fit")
    ax.plot(flc_profile.distances, flc_profile.values, "s", label="FLC data", color="tab:blue")
    ax.plot(flc_profile.distances, exponential_trail_model(flc_profile.distances, flc_fit.amplitude, flc_fit.length, flc_fit.offset), "-", color="tab:blue", label="FLC fit")
    ax.set_xlabel("Parallel transfer distance from source (pixels)")
    ax.set_ylabel("Counts (electrons)")
    ax.set_title("FLT vs FLC trail profile — SYNTHETIC DEMO (n=1 source)")
    ax.legend()
    path = _save(fig, out_dir, "fig03_flt_vs_flc_profiles")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="electrons vs pixels", config_path=config_path,
             extra={"flt_amplitude": flt_fit.amplitude, "flc_amplitude": flc_fit.amplitude})

    # 4 & 5: suppression vs charge, residual vs transfer distance (multi-source synthetic sample)
    rng_fluxes = [6000.0, 10000.0, 15000.0, 20000.0, 26000.0, 32000.0]
    rows_y = [40, 55, 70, 85, 100, 110]
    charges, distances, suppressions = [], [], []
    for i, (flux, y) in enumerate(zip(rng_fluxes, rows_y)):
        src = SyntheticSource(50, y, flux)
        f_hdul = build_synthetic_acs_hdulist(seed=20260713 + i, sources=(src,), parallel_trail=SyntheticTrailSpec(0.05, 6.0), serial_trail=None, inject_hot_pixels=0)
        c_hdul = build_synthetic_acs_hdulist(seed=20260713 + i, sources=(src,), parallel_trail=SyntheticTrailSpec(0.01, 6.0), serial_trail=None, inject_hot_pixels=0)
        geom_i = infer_geometry(dict(f_hdul[0].header) | dict(f_hdul["SCI"].header))
        fp = extract_parallel_trail(f_hdul["SCI"].data, geom_i, src.x, src.y)
        cp = extract_parallel_trail(c_hdul["SCI"].data, geom_i, src.x, src.y)
        ff, cf = fit_exponential_trail(fp), fit_exponential_trail(cp)
        suppression = 1 - (cf.amplitude * cf.length) / (ff.amplitude * ff.length)
        charges.append(flux)
        distances.append(geom_i.parallel_transfer_distance(np.array([src.y]))[0])
        suppressions.append(suppression)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(charges, suppressions, "o-")
    ax.set_xlabel("Source charge (electrons)")
    ax.set_ylabel("Trail-charge suppression fraction (FLC vs FLT)")
    ax.set_title(f"Suppression vs source charge — SYNTHETIC DEMO (n={len(charges)} sources)")
    ax.set_ylim(0, 1)
    path = _save(fig, out_dir, "fig04_suppression_vs_charge")
    _sidecar(path, data_kind=data_kind, sample_size=len(charges), units="electrons vs dimensionless", config_path=config_path)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(distances, suppressions, "o-", color="tab:green")
    ax.set_xlabel("Parallel transfer distance (pixels)")
    ax.set_ylabel("Trail-charge suppression fraction (FLC vs FLT)")
    ax.set_title(f"Suppression vs transfer distance — SYNTHETIC DEMO (n={len(distances)} sources)")
    ax.set_ylim(0, 1)
    path = _save(fig, out_dir, "fig05_residual_vs_transfer_distance")
    _sidecar(path, data_kind=data_kind, sample_size=len(distances), units="pixels vs dimensionless", config_path=config_path)

    # 6. injection recovery
    truth_amplitudes = np.array([200.0, 400.0, 800.0, 1200.0, 1600.0])
    recovered_amplitudes = []
    for i, amp in enumerate(truth_amplitudes):
        src = SyntheticSource(50, 90, 20000.0)
        spec = SyntheticTrailSpec(float(amp / src.flux), 6.0)
        hdul_i = build_synthetic_acs_hdulist(seed=30000 + i, sources=(src,), parallel_trail=spec, serial_trail=None, inject_hot_pixels=0)
        geom_i = infer_geometry(dict(hdul_i[0].header) | dict(hdul_i["SCI"].header))
        profile_i = extract_parallel_trail(hdul_i["SCI"].data, geom_i, src.x, src.y)
        fit_i = fit_exponential_trail(profile_i)
        recovered_amplitudes.append(fit_i.amplitude)

    fig, ax = plt.subplots(figsize=(6, 6))
    lims = [0, float(truth_amplitudes.max()) * 1.1]
    ax.plot(lims, lims, "k--", label="1:1")
    ax.plot(truth_amplitudes, recovered_amplitudes, "o", color="tab:red", label="recovered vs injected")
    ax.set_xlabel("Injected trail amplitude (electrons)")
    ax.set_ylabel("Recovered trail amplitude (electrons)")
    ax.set_title(f"Injection-recovery validation — SYNTHETIC DEMO (n={len(truth_amplitudes)})")
    ax.legend()
    path = _save(fig, out_dir, "fig06_injection_recovery")
    _sidecar(path, data_kind=data_kind, sample_size=len(truth_amplitudes), units="electrons", config_path=config_path)

    print(f"Wrote 6 demo figures (SVG+PNG+JSON) to {out_dir}")


def make_real_figures(out_dir: Path, config_path: Path, manifest_path: Path, raw_dir: Path) -> None:
    config = load_config(config_path)
    manifest_rows = read_manifest(manifest_path)
    if not manifest_rows:
        raise SystemExit(
            "data/manifest.csv has no rows. Run scripts/fetch_data.py (with explicit "
            "operator authorization) and scripts/run_analysis.py before generating real figures."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    data_kind = config.input.data_mode

    pairs = pair_flt_flc(manifest_rows, raw_dir)
    result = run_pipeline(manifest_rows, raw_dir, config)

    first_pair = pairs[0]
    flt = load_exposure(first_pair.flt_path)
    flc = load_exposure(first_pair.flc_path)

    # 1. detector geometry (from the real header)
    geometry = flt.geometry
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.add_patch(plt.Rectangle((0, 0), geometry.naxis1, geometry.naxis2, fill=False, edgecolor="black"))
    ax.plot(geometry.readout_col, geometry.readout_row, "rs", markersize=10, label="Readout amplifier (header-derived)")
    ax.set_xlabel("Column (pixels, serial axis)")
    ax.set_ylabel("Row (pixels, parallel axis)")
    ax.set_title(f"Detector geometry: {first_pair.rootname}\n(CCDAMP={geometry.ccdamp}, CCDCHIP={geometry.ccdchip})", fontsize=11)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    path = _save(fig, out_dir, "fig01_detector_geometry")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="pixels", config_path=config_path)

    # 2 & 3. example trails and FLT vs FLC profiles: try several bright candidates
    # and use the first one whose FLT and FLC trails both fit successfully — the
    # single brightest source is not guaranteed to have a well-conditioned fit
    # (e.g. saturation, blending, cosmic-ray contamination), matching the same
    # per-source failure handling used in the main pipeline (core._measure_pair).
    candidates = detect_sources(flc.science_array, brightest=15)
    src = None
    flt_profile = flc_profile = flt_fit = flc_fit = None
    for candidate in candidates:
        try:
            cand_flt_profile = extract_parallel_trail(flt.science_array, flt.geometry, candidate.x, candidate.y)
            cand_flc_profile = extract_parallel_trail(flc.science_array, flc.geometry, candidate.x, candidate.y)
            cand_flt_fit = fit_exponential_trail(cand_flt_profile)
            cand_flc_fit = fit_exponential_trail(cand_flc_profile)
        except (InsufficientDataError, ConvergenceError):
            continue
        src, flt_profile, flc_profile, flt_fit, flc_fit = (
            candidate, cand_flt_profile, cand_flc_profile, cand_flt_fit, cand_flc_fit,
        )
        break
    if src is None:
        raise ConvergenceError(
            f"none of the {len(candidates)} brightest candidate sources in {first_pair.rootname} "
            "had a converging FLT+FLC trail fit"
        )

    y0, y1 = max(0, int(src.y) - 25), min(geometry.naxis2, int(src.y) + 5)
    x0, x1 = max(0, int(src.x) - 15), min(geometry.naxis1, int(src.x) + 15)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5), sharey=True)
    for ax, exp, label in ((axes[0], flt, "FLT (uncorrected)"), (axes[1], flc, "FLC (CTE-corrected)")):
        im = ax.imshow(exp.science_array[y0:y1, x0:x1], origin="lower", cmap="viridis")
        ax.set_title(label)
        ax.set_xlabel("Column offset (pixels)")
    axes[0].set_ylabel("Row offset (pixels)")
    fig.suptitle(f"Example parallel CTE trail: {first_pair.rootname}")
    fig.colorbar(im, ax=axes, shrink=0.8, label="Counts (electrons)")
    path = _save(fig, out_dir, "fig02_example_trails")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="electrons", config_path=config_path)

    # 3. FLT vs FLC profiles for the same source
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(flt_profile.distances, flt_profile.values, "o", label="FLT data", color="tab:orange")
    ax.plot(flt_profile.distances, exponential_trail_model(flt_profile.distances, flt_fit.amplitude, flt_fit.length, flt_fit.offset), "-", color="tab:orange", label="FLT fit")
    ax.plot(flc_profile.distances, flc_profile.values, "s", label="FLC data", color="tab:blue")
    ax.plot(flc_profile.distances, exponential_trail_model(flc_profile.distances, flc_fit.amplitude, flc_fit.length, flc_fit.offset), "-", color="tab:blue", label="FLC fit")
    ax.set_xlabel("Parallel transfer distance from source (pixels)")
    ax.set_ylabel("Counts (electrons)")
    ax.set_title(f"FLT vs FLC trail profile: {first_pair.rootname}")
    ax.legend()
    path = _save(fig, out_dir, "fig03_flt_vs_flc_profiles")
    _sidecar(path, data_kind=data_kind, sample_size=1, units="electrons vs pixels", config_path=config_path)

    # 4. suppression vs charge (from the full pipeline result)
    charges = [m.flux for m in result.measurements]
    suppressions = [m.suppression.suppression_fraction for m in result.measurements]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(charges, suppressions, "o")
    ax.set_xlabel("Source charge (DAOStarFinder flux estimate)")
    ax.set_ylabel("Trail-charge suppression fraction (FLC vs FLT)")
    ax.set_title(f"Suppression vs source charge (n={len(charges)} sources)")
    path = _save(fig, out_dir, "fig04_suppression_vs_charge")
    _sidecar(path, data_kind=data_kind, sample_size=len(charges), units="dimensionless vs dimensionless", config_path=config_path)

    # 5. residual vs transfer distance
    tdist = [m.parallel_transfer_distance for m in result.measurements]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(tdist, suppressions, "o", color="tab:green")
    ax.set_xlabel("Parallel transfer distance (pixels)")
    ax.set_ylabel("Trail-charge suppression fraction (FLC vs FLT)")
    ax.set_title(f"Suppression vs transfer distance (n={len(tdist)} sources)")
    path = _save(fig, out_dir, "fig05_residual_vs_transfer_distance")
    _sidecar(path, data_kind=data_kind, sample_size=len(tdist), units="pixels vs dimensionless", config_path=config_path)

    # 6. injection recovery (synthetic gate, run against the real config/thresholds)
    truth_amplitudes = np.array([200.0, 400.0, 800.0, 1200.0, 1600.0])
    recovered_amplitudes = []
    for i, amp in enumerate(truth_amplitudes):
        s = SyntheticSource(50, 90, 20000.0)
        spec = SyntheticTrailSpec(float(amp / s.flux), 6.0)
        hdul_i = build_synthetic_acs_hdulist(seed=30000 + i, sources=(s,), parallel_trail=spec, serial_trail=None, inject_hot_pixels=0)
        geom_i = infer_geometry(dict(hdul_i[0].header) | dict(hdul_i["SCI"].header))
        profile_i = extract_parallel_trail(hdul_i["SCI"].data, geom_i, s.x, s.y)
        fit_i = fit_exponential_trail(profile_i)
        recovered_amplitudes.append(fit_i.amplitude)
    fig, ax = plt.subplots(figsize=(6, 6))
    lims = [0, float(truth_amplitudes.max()) * 1.1]
    ax.plot(lims, lims, "k--", label="1:1")
    ax.plot(truth_amplitudes, recovered_amplitudes, "o", color="tab:red", label="recovered vs injected")
    ax.set_xlabel("Injected trail amplitude (electrons)")
    ax.set_ylabel("Recovered trail amplitude (electrons)")
    ax.set_title(f"Injection-recovery validation gate (n={len(truth_amplitudes)}, run alongside real data)")
    ax.legend()
    path = _save(fig, out_dir, "fig06_injection_recovery")
    _sidecar(path, data_kind="synthetic_validation_gate", sample_size=len(truth_amplitudes), units="electrons", config_path=config_path)

    print(f"Wrote 6 real-data figures (SVG+PNG+JSON) to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=Path("figures"))
    parser.add_argument("--config", type=Path, default=Path("config/analysis.yml"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()

    if args.demo:
        # Preserve the original single-panel smoke plot for the fastest possible check.
        from hst_acs_two_axis_cte_audit.core import demo_series

        plot_demo(demo_series(), args.out_dir / "fig00_smoke_test.png")
        make_demo_figures(args.out_dir, args.config)
        return

    make_real_figures(args.out_dir, args.config, args.manifest, args.raw_dir)


if __name__ == "__main__":
    main()
