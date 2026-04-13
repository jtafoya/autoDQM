"""
Visualization for training and anomaly detection output.

Subcommands:
    python3 -m src.plot reference              — reference model statistics
    python3 -m src.plot file <csv_path>        — per-channel anomaly analysis of one file
    python3 -m src.plot log [--log-file ...]   — summary of the anomaly log over time

All figures are saved to --out-dir (default: plots/).
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

from .config import load_config
from .reference import ReferenceModel
from .detector import AnomalyDetector
from .features import extract_features, METRIC_COLS

# ── shared style ────────────────────────────────────────────────────────────

plt.rcParams.update({
    "figure.dpi": 150,
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
})

CMAP_ZSCORE  = "YlOrRd"
CMAP_BIPOLAR = "RdBu_r"
CMAP_SEQ     = "viridis"


# ══════════════════════════════════════════════════════════════════════════════
# 1.  REFERENCE PLOTS
# ══════════════════════════════════════════════════════════════════════════════

def plot_reference(ref: ReferenceModel, out_dir: Path) -> None:
    """Three figures summarising the trained reference model."""
    channels  = sorted(ref.known_channels(), key=str)
    feat_cols = ref._feat_cols

    means = np.array([ref.get_stats(c)[0] for c in channels])   # (n_ch, n_feat)
    stds  = np.array([ref.get_stats(c)[1] for c in channels])
    counts = np.array([ref.n_files(c) for c in channels])

    # ── 1a. Reference mean heatmap ───────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(18, 6))
    # Z-score normalise each feature column so the colour scale is comparable
    means_norm = (means - means.mean(0)) / (means.std(0) + 1e-9)
    im = ax.imshow(means_norm.T, aspect="auto", cmap=CMAP_BIPOLAR,
                   vmin=-3, vmax=3)
    ax.set_xlabel("Channel")
    ax.set_ylabel("Feature")
    ax.set_xticks(range(len(channels)))
    ax.set_xticklabels(channels, fontsize=6, rotation=90)
    ax.set_yticks(range(len(feat_cols)))
    ax.set_yticklabels(feat_cols, fontsize=7)
    ax.set_title("Reference means (column-normalised z-score)")
    fig.colorbar(im, ax=ax, label="z-score relative to feature mean")
    fig.tight_layout()
    _save(fig, out_dir / "reference_means.png")

    # ── 1b. Reference std heatmap ────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(18, 6))
    # Normalise stds by their per-feature median so scale is comparable
    stds_norm = stds / (np.median(stds, axis=0) + 1e-9)
    im = ax.imshow(np.log1p(stds_norm).T, aspect="auto", cmap=CMAP_SEQ)
    ax.set_xlabel("Channel")
    ax.set_ylabel("Feature")
    ax.set_xticks(range(len(channels)))
    ax.set_xticklabels(channels, fontsize=6, rotation=90)
    ax.set_yticks(range(len(feat_cols)))
    ax.set_yticklabels(feat_cols, fontsize=7)
    ax.set_title("Reference uncertainty — log(1 + σ / median_σ per feature)")
    fig.colorbar(im, ax=ax, label="log-normalised std")
    fig.tight_layout()
    _save(fig, out_dir / "reference_stds.png")

    # ── 1c. Training coverage ────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.bar(range(len(channels)), counts, color="steelblue", width=0.8)
    ax.set_xlabel("Channel")
    ax.set_ylabel("Training files")
    ax.set_xticks(range(len(channels)))
    ax.set_xticklabels(channels, fontsize=6, rotation=90)
    ax.set_title("Training coverage — number of good files each channel appeared in")
    ax.axhline(np.mean(counts), color="tomato", linestyle="--", linewidth=1,
               label=f"mean = {np.mean(counts):.1f}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, out_dir / "reference_coverage.png")

    print(f"  Reference plots saved to {out_dir}/")


def plot_mean_table(ref: ReferenceModel, out_dir: Path) -> None:
    """
    Heatmap table of per-channel reference mean feature values.

    Rows = channels (integer channels first, pseudo-channels last).
    Columns = features, grouped as: digitizer metrics | LVDS pin | trigger | trigger_lvds_total.
    Cell colour = per-column min-max normalisation so every feature's variation
    across channels is visible regardless of its absolute scale.
    Cell text = actual mean value in a compact format.
    """
    from .features import PSEUDO_TRIGGER, PSEUDO_LVDS

    all_channels = sorted(ref.known_channels(), key=str)
    # Real channels first, then trigger_rate, then trigger_lvds_total at the very bottom
    real_channels = sorted([c for c in all_channels if isinstance(c, int)])
    trigger_row   = [PSEUDO_TRIGGER] if PSEUDO_TRIGGER in all_channels else []
    lvds_row      = [PSEUDO_LVDS]    if PSEUDO_LVDS    in all_channels else []
    pseudo_channels = trigger_row + lvds_row
    channels  = real_channels + pseudo_channels
    feat_cols = ref._feat_cols

    n_ch   = len(channels)
    n_feat = len(feat_cols)

    # Build raw mean matrix  (n_ch × n_feat)
    means = np.full((n_ch, n_feat), np.nan)
    for i, ch in enumerate(channels):
        stats = ref.get_stats(ch)
        if stats is not None:
            means[i] = stats[0]

    # Per-column min-max normalisation for colour scale
    col_min   = np.nanmin(means, axis=0)
    col_max   = np.nanmax(means, axis=0)
    col_range = col_max - col_min
    col_range[col_range < 1e-12] = 1.0          # constant feature → midpoint colour
    means_norm = (means - col_min) / col_range   # [0, 1], NaN stays NaN

    # Figure sizing: give each cell ~0.5 × 0.22 inches
    cell_w = 0.50
    cell_h = 0.22
    fig_w  = max(16, n_feat * cell_w + 4.0)
    fig_h  = max( 8, n_ch   * cell_h + 2.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Draw heatmap (NaN cells come out white)
    cmap = plt.get_cmap("YlOrRd").copy()
    cmap.set_bad(color="#f0f0f0")              # light grey for NaN / no-data cells
    im = ax.imshow(means_norm, aspect="auto", cmap=cmap, vmin=0, vmax=1,
                   interpolation="nearest")

    # Annotate every cell with the raw mean value
    def _fmt(v: float) -> str:
        if np.isnan(v):
            return ""
        if v == 0.0:
            return "0"
        a = abs(v)
        if a >= 1e4 or a < 1e-2:
            return f"{v:.1e}"
        if a >= 100:
            return f"{v:.1f}"
        if a >= 10:
            return f"{v:.2f}"
        return f"{v:.3g}"

    for i in range(n_ch):
        for j in range(n_feat):
            txt = _fmt(means[i, j])
            if not txt:
                continue
            # Use white text on dark cells, black on light cells
            norm_val = means_norm[i, j]
            text_color = "white" if (not np.isnan(norm_val) and norm_val > 0.65) else "black"
            ax.text(j, i, txt, ha="center", va="center",
                    fontsize=5, color=text_color, clip_on=True)

    # Separator line between real and pseudo-channels
    if pseudo_channels:
        sep = len(real_channels) - 0.5
        ax.axhline(sep, color="steelblue", linewidth=1.5, linestyle="--")

    # Axis tick labels
    ax.set_xticks(range(n_feat))
    ax.set_xticklabels(feat_cols, fontsize=6, rotation=45, ha="right")
    ax.set_yticks(range(n_ch))
    ax.set_yticklabels(
        [f"ch{c}" if isinstance(c, int) else c for c in channels],
        fontsize=6,
    )

    ax.set_title(
        f"Reference mean feature values — {len(real_channels)} digitiser channels, "
        f"{len(feat_cols)} features  (colour scale: per-feature min→max)",
        fontsize=9,
    )
    ax.set_xlabel("Feature", fontsize=8)
    ax.set_ylabel("Digitiser", fontsize=8)

    fig.colorbar(im, ax=ax, label="Relative value within feature (0=min, 1=max)",
                 shrink=0.4, pad=0.01)
    fig.tight_layout()
    _save(fig, out_dir / "reference_mean_table.png")


# ══════════════════════════════════════════════════════════════════════════════
# 2.  SINGLE-FILE ANALYSIS PLOTS
# ══════════════════════════════════════════════════════════════════════════════

def plot_file(filepath: str, detector: AnomalyDetector, out_dir: Path) -> None:
    """Four figures for the anomaly analysis of one Digitizer CSV file."""
    stem     = Path(filepath).stem
    ref      = detector.reference
    feat_cols = ref._feat_cols

    results  = detector.analyze_file(filepath)
    features = extract_features(filepath)
    z_df     = ref.z_score(features)

    # Read geometry from raw CSV (channel → row, column, layer)
    raw = pd.read_csv(filepath)
    geom = (raw.groupby("channel")[["row", "column", "layer"]]
               .first()
               .reset_index())

    channels = sorted(results.index.tolist(), key=str)

    # ── 2a. Z-score heatmap ──────────────────────────────────────────────────
    z_matrix = np.full((len(channels), len(feat_cols)), np.nan)
    ch_idx   = {ch: i for i, ch in enumerate(channels)}
    for ch in channels:
        if ch in z_df.index and not z_df.loc[ch].isna().all():
            z_matrix[ch_idx[ch]] = np.clip(z_df.loc[ch].abs().values, 0, 50)

    fig, ax = plt.subplots(figsize=(18, max(4, len(channels) * 0.18)))
    im = ax.imshow(z_matrix, aspect="auto", cmap=CMAP_ZSCORE, vmin=0, vmax=10)
    # Overlay red border on anomalous channels
    for ch in channels:
        if results.loc[ch, "anomalous"]:
            i = ch_idx[ch]
            ax.axhspan(i - 0.5, i + 0.5, color="none",
                       linewidth=0, alpha=0)   # placeholder
            for spine in ["left", "right", "top", "bottom"]:
                pass  # drawn per-cell below
    # Highlight anomalous rows with a left margin bar
    for ch in channels:
        if results.loc[ch, "anomalous"]:
            i = ch_idx[ch]
            ax.barh(i, len(feat_cols), left=0, height=0.95,
                    color="tomato", alpha=0.08, zorder=0)
    ax.set_xlabel("Feature")
    ax.set_ylabel("Channel")
    ax.set_xticks(range(len(feat_cols)))
    ax.set_xticklabels(feat_cols, fontsize=6.5, rotation=45, ha="right")
    ax.set_yticks(range(len(channels)))
    ax.set_yticklabels(channels, fontsize=6)
    ax.set_title(f"Z-score heatmap — {stem}\n"
                 f"(clamped at 50σ; red shading = flagged channel)")
    fig.colorbar(im, ax=ax, label="|z-score|")
    fig.tight_layout()
    _save(fig, out_dir / f"{stem}_zscore_heatmap.png")

    # ── 2b. Max |z| per channel ──────────────────────────────────────────────
    max_z   = results["max_z"].fillna(0).values
    colors  = ["tomato" if a else "steelblue"
               for a in results.loc[channels, "anomalous"]]
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.bar(range(len(channels)), max_z, color=colors, width=0.8)
    ax.axhline(detector.z_threshold, color="black", linestyle="--", linewidth=1,
               label=f"threshold = {detector.z_threshold}σ")
    ax.set_xlabel("Channel")
    ax.set_ylabel("Max |z-score|")
    ax.set_xticks(range(len(channels)))
    ax.set_xticklabels(channels, fontsize=6, rotation=90)
    ax.set_title(f"Max |z-score| per channel — {stem}\n"
                 f"(red = flagged, blue = nominal)")
    ax.set_yscale("symlog", linthresh=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, out_dir / f"{stem}_max_zscore.png")

    # ── 2c. Isolation Forest score per channel ───────────────────────────────
    if_scores = results["if_score"].values
    if not np.all(np.isnan(if_scores)):
        if_colors = ["tomato" if f else "steelblue"
                     for f in results.loc[channels, "if_flag"]
                     if "if_flag" in results.columns] if "if_flag" in results.columns \
                    else ["steelblue"] * len(channels)

        fig, ax = plt.subplots(figsize=(14, 4))
        ax.bar(range(len(channels)), if_scores, color="steelblue", width=0.8)
        ax.set_xlabel("Channel")
        ax.set_ylabel("IF anomaly score")
        ax.set_xticks(range(len(channels)))
        ax.set_xticklabels(channels, fontsize=6, rotation=90)
        ax.set_title(f"Isolation Forest anomaly score per channel — {stem}\n"
                     f"(more negative = more anomalous)")
        fig.tight_layout()
        _save(fig, out_dir / f"{stem}_if_scores.png")

    # ── 2d. Detector geometry map ────────────────────────────────────────────
    geom = geom[geom["channel"].isin(channels)].copy()
    geom["max_z"]    = geom["channel"].map(results["max_z"].to_dict()).fillna(0)
    geom["anomalous"] = geom["channel"].map(results["anomalous"].to_dict())

    layers = sorted(geom["layer"].unique())
    ncols  = len(layers)
    nrows  = 1
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(5 * ncols, 4 * nrows + 0.5),
                             squeeze=False)
    vmax = max(geom["max_z"].max(), detector.z_threshold + 1)

    for idx, layer in enumerate(layers):
        ax  = axes[idx // ncols][idx % ncols]
        sub = geom[geom["layer"] == layer]
        sc  = ax.scatter(sub["column"], sub["row"],
                         c=sub["max_z"].clip(0, vmax),
                         cmap=CMAP_ZSCORE, vmin=0, vmax=vmax,
                         s=200, edgecolors="black", linewidths=0.4, zorder=3)
        # Ring around flagged channels
        flagged = sub[sub["anomalous"]]
        if not flagged.empty:
            ax.scatter(flagged["column"], flagged["row"],
                       s=320, facecolors="none",
                       edgecolors="red", linewidths=1.5, zorder=4)
        ax.set_title(f"Layer {layer}")
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        ax.invert_yaxis()
        fig.colorbar(sc, ax=ax, label="|z|")

    # Hide unused axes
    for idx in range(len(layers), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.suptitle(f"Detector geometry map — {stem}\n"
                 f"(colour = max |z|, red ring = flagged channel)", y=1.01)
    fig.tight_layout()
    _save(fig, out_dir / f"{stem}_geometry.png")

    print(f"  File plots saved to {out_dir}/")


# ══════════════════════════════════════════════════════════════════════════════
# 3.  LOG SUMMARY PLOTS
# ══════════════════════════════════════════════════════════════════════════════

def _run_subrun_key(filename: str):
    """Return (run, subrun) ints parsed from a Digitizer filename, or (inf, inf) if unparseable."""
    import re
    m = re.search(r"Digitizer_run(\d+)_subrun(\d+)", str(filename), re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    return (float("inf"), float("inf"))


def plot_log(log_path: str, out_dir: Path, file_alert_threshold: float = 0.001) -> None:
    """Four figures summarising the anomaly log."""
    df = pd.read_csv(log_path)
    if df.empty:
        print("ERROR: Log file is empty.", file=sys.stderr)
        return

    # ── 3a. Anomalous channel fraction per file ──────────────────────────────
    per_file = (df.groupby("filename")
                  .agg(total=("channel", "count"),
                       n_anomalous=("anomalous", "sum"))
                  .assign(frac=lambda x: x["n_anomalous"] / x["total"])
                  .reset_index())

    # Sort by run number then subrun number
    per_file["_sort_key"] = per_file["filename"].apply(_run_subrun_key)
    per_file = per_file.sort_values("_sort_key").drop(columns="_sort_key").reset_index(drop=True)

    n_files = len(per_file)
    # Cap width to avoid matplotlib's 2^16 pixel limit at 150 DPI (~436 inches).
    # Above 150 files the x-labels become unreadable anyway, so drop them.
    LABEL_THRESHOLD = 150
    fig_w = min(max(8, n_files * 0.5), 80)
    fig, ax = plt.subplots(figsize=(fig_w, 4))
    colors = ["tomato" if f >= file_alert_threshold else "steelblue" for f in per_file["frac"]]
    ax.bar(range(n_files), per_file["frac"] * 100, color=colors, width=0.8)
    ax.axhline(file_alert_threshold * 100, color="black", linestyle="--", linewidth=1,
               label=f"{file_alert_threshold:.1%} alert threshold")
    ax.set_ylabel("Anomalous channels (%)")
    if n_files <= LABEL_THRESHOLD:
        ax.set_xticks(range(n_files))
        ax.set_xticklabels(per_file["filename"], fontsize=6, rotation=45, ha="right")
        ax.set_xlabel("File (sorted by run / subrun)")
    else:
        ax.set_xticks([])
        ax.set_xlabel(f"File (sorted by run / subrun) — {n_files} files, labels hidden above {LABEL_THRESHOLD}")
    ax.set_ylim(0, 105)
    ax.set_title("Anomalous channel fraction per file\n"
                 "(red = above alert threshold)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, out_dir / "log_anomaly_rate.png")

    # ── 3b. Most frequently anomalous channels ───────────────────────────────
    anomalous_df = df[df["anomalous"]]
    if anomalous_df.empty:
        print("  No anomalous channels in log — skipping channel frequency plot.")
    else:
        ch_counts = (anomalous_df.groupby("channel").size()
                                 .sort_values(ascending=False)
                                 .head(40))
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.bar(range(len(ch_counts)), ch_counts.values, color="tomato", width=0.8)
        ax.set_xlabel("Channel")
        ax.set_ylabel("Times flagged")
        ax.set_xticks(range(len(ch_counts)))
        ax.set_xticklabels(ch_counts.index, fontsize=8, rotation=90)
        ax.set_title("Most frequently anomalous channels (top 40)")
        fig.tight_layout()
        _save(fig, out_dir / "log_channel_frequency.png")

    # ── 3c. Feature trigger frequency ───────────────────────────────────────
    triggered = (df["triggered_features"]
                   .dropna()
                   .str.split(";")
                   .explode()
                   .str.strip())
    triggered = triggered[triggered != ""]
    if triggered.empty:
        print("  No triggered features in log — skipping feature frequency plot.")
    else:
        feat_counts = triggered.value_counts().head(20)
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.barh(range(len(feat_counts)), feat_counts.values[::-1],
                color="darkorange")
        ax.set_yticks(range(len(feat_counts)))
        ax.set_yticklabels(feat_counts.index[::-1], fontsize=8)
        ax.set_xlabel("Times triggered")
        ax.set_title("Most frequently triggered features (top 20)")
        fig.tight_layout()
        _save(fig, out_dir / "log_feature_frequency.png")

    # ── 3d. Per-run good-subrun fraction ─────────────────────────────────────
    per_file["_run"]    = per_file["filename"].apply(lambda f: _run_subrun_key(f)[0])
    per_file["_subrun"] = per_file["filename"].apply(lambda f: _run_subrun_key(f)[1])
    parseable = per_file[per_file["_run"] != float("inf")].copy()

    if parseable.empty:
        print("  No parseable run/subrun filenames — skipping run summary plot.")
    else:
        parseable["is_good"] = parseable["frac"] < file_alert_threshold
        run_stats = (
            parseable.groupby("_run")
                     .agg(n_subruns=("filename", "count"),
                          n_good=("is_good", "sum"))
                     .assign(pct_good=lambda x: x["n_good"] / x["n_subruns"] * 100)
                     .reset_index()
                     .sort_values("_run")
        )

        n_runs = len(run_stats)
        fig_w  = max(8, n_runs * 1.0)
        fig, ax = plt.subplots(figsize=(fig_w, 4))
        bar_colors = [
            "steelblue" if p == 100 else ("tomato" if p == 0 else "darkorange")
            for p in run_stats["pct_good"]
        ]
        bars = ax.bar(range(n_runs), run_stats["pct_good"],
                      color=bar_colors, width=0.6, edgecolor="white", linewidth=0.5)

        # Annotate each bar with "good/total"
        for i, row in enumerate(run_stats.itertuples()):
            ax.text(i, min(row.pct_good + 2, 103),
                    f"{int(row.n_good)}/{int(row.n_subruns)}",
                    ha="center", va="bottom", fontsize=7)

        ax.set_xlim(-0.5, n_runs - 0.5)
        ax.set_ylim(0, 115)
        ax.set_ylabel("Good subruns (%)")
        ax.set_xticks(range(n_runs))
        ax.set_xticklabels([f"run{int(r)}" for r in run_stats["_run"]],
                           rotation=45, ha="right", fontsize=8)
        ax.axhline(100, color="steelblue", linestyle=":", linewidth=0.8, alpha=0.5)
        ax.set_title(
            f"Good subrun fraction per run  "
            f"(threshold: {file_alert_threshold:.0%} anomalous channels)\n"
            f"blue = all good · orange = partial · red = all bad"
        )
        fig.tight_layout()
        _save(fig, out_dir / "log_run_summary.png")

    print(f"  Log plots saved to {out_dir}/")


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _save(fig: plt.Figure, path: Path) -> None:
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"    {path.name}")


def _load_models(models_dir: str):
    models_path = Path(models_dir)
    ref_path = models_path / "reference.npz"
    det_path = models_path / "detector.pkl"
    if not ref_path.exists() or not det_path.exists():
        print(f"ERROR: Models not found in {models_dir}. Run train.py first.",
              file=sys.stderr)
        sys.exit(1)
    ref      = ReferenceModel.load(str(ref_path))
    detector = AnomalyDetector.load(str(det_path), ref)
    return detector


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    _pre = argparse.ArgumentParser(add_help=False)
    _pre.add_argument("--config", default="config.json")
    cfg = load_config(_pre.parse_known_args()[0].config)

    tag = cfg["model_tag"]

    parser = argparse.ArgumentParser(
        description="Generate visualizations for training and anomaly detection output."
    )
    parser.add_argument("--config", default="config.json",
                        help="Path to JSON configuration file (default: config.json)")
    parser.add_argument("--models-dir", help="Directory with saved models")
    parser.add_argument("--out-dir",    help="Directory to save figures")

    parser.set_defaults(
        models_dir = str(Path(cfg["models_dir"]) / tag),
        out_dir    = str(Path(cfg["plots_dir"])  / tag),
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("reference", help="Plot reference model statistics")

    p_file = sub.add_parser("file", help="Plot anomaly analysis of a single CSV file")
    p_file.add_argument("csv", help="Path to Digitizer CSV file")

    p_log = sub.add_parser("log", help="Plot summary of the anomaly log")
    p_log.add_argument("--log-file",
                       default=str(Path(cfg["logs_dir"]) / f"{tag}.csv"),
                       help="Path to the anomaly log CSV")
    p_log.add_argument("--file-alert-threshold", type=float,
                       default=cfg["file_alert_threshold"],
                       help="Anomalous channel fraction that marks a subrun as bad")

    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log_file_str = getattr(args, "log_file", "n/a")
    from .config import print_banner
    print_banner("plot", args.config, [
        ("subcommand",           args.command),
        ("models dir",           args.models_dir),
        ("out dir",              str(out_dir)),
        ("log file",             log_file_str),
    ])

    if args.command == "reference":
        detector = _load_models(args.models_dir)
        plot_reference(detector.reference, out_dir)

    elif args.command == "file":
        detector = _load_models(args.models_dir)
        plot_file(args.csv, detector, out_dir)

    elif args.command == "log":
        if not Path(args.log_file).exists():
            print(f"ERROR: Log file not found: {args.log_file}", file=sys.stderr)
            sys.exit(1)
        plot_log(args.log_file, out_dir, file_alert_threshold=args.file_alert_threshold)


if __name__ == "__main__":
    main()
