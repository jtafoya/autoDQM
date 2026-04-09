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
    channels  = sorted(ref.known_channels())
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

    channels = sorted(results.index.tolist())

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

def plot_log(log_path: str, out_dir: Path) -> None:
    """Three figures summarising the anomaly log over time."""
    df = pd.read_csv(log_path, parse_dates=["timestamp"])
    if df.empty:
        print("ERROR: Log file is empty.", file=sys.stderr)
        return

    # ── 3a. Anomalous channel fraction per file ──────────────────────────────
    per_file = (df.groupby("filename")
                  .agg(total=("channel", "count"),
                       n_anomalous=("anomalous", "sum"),
                       timestamp=("timestamp", "first"))
                  .assign(frac=lambda x: x["n_anomalous"] / x["total"])
                  .sort_values("timestamp")
                  .reset_index())

    fig, ax = plt.subplots(figsize=(max(8, len(per_file) * 0.5), 4))
    colors = ["tomato" if f >= 0.20 else "steelblue" for f in per_file["frac"]]
    ax.bar(range(len(per_file)), per_file["frac"] * 100, color=colors, width=0.8)
    ax.axhline(20, color="black", linestyle="--", linewidth=1,
               label="20% alert threshold")
    ax.set_xlabel("File (chronological)")
    ax.set_ylabel("Anomalous channels (%)")
    ax.set_xticks(range(len(per_file)))
    ax.set_xticklabels(per_file["filename"], fontsize=6, rotation=45, ha="right")
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
    parser = argparse.ArgumentParser(
        description="Generate visualizations for training and anomaly detection output."
    )
    parser.add_argument("--models-dir", default="models", help="Directory with saved models")
    parser.add_argument("--out-dir",    default="plots",  help="Directory to save figures")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("reference", help="Plot reference model statistics")

    p_file = sub.add_parser("file", help="Plot anomaly analysis of a single CSV file")
    p_file.add_argument("csv", help="Path to Digitizer CSV file")

    p_log = sub.add_parser("log", help="Plot summary of the anomaly log")
    p_log.add_argument("--log-file", default="logs/anomalies.csv",
                       help="Path to the anomaly log CSV")

    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

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
        plot_log(args.log_file, out_dir)


if __name__ == "__main__":
    main()
