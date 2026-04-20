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

from .args import preparse_config, add_config
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


def _fmt(v: float) -> str:
    """Compact cell annotation: scientific for very large/small, fixed decimals otherwise."""
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


def _channel_order(index, pseudo_trigger, pseudo_lvds):
    """Return channels sorted: integers numerically, then trigger_rate, then trigger_lvds_total."""
    real = sorted([c for c in index if isinstance(c, int)])
    pseudo = [c for c in [pseudo_trigger, pseudo_lvds] if c in index]
    return real + pseudo


# ══════════════════════════════════════════════════════════════════════════════
# 1.  REFERENCE PLOTS
# ══════════════════════════════════════════════════════════════════════════════

def plot_reference(ref: ReferenceModel, out_dir: Path) -> None:
    """Three figures summarising the trained reference model."""
    from .features import PSEUDO_TRIGGER, PSEUDO_LVDS
    channels  = _channel_order(ref.known_channels(), PSEUDO_TRIGGER, PSEUDO_LVDS)
    feat_cols = ref._feat_cols

    means  = np.array([ref.get_stats(c)[0] for c in channels])   # (n_ch, n_feat)
    stds   = np.array([ref.get_stats(c)[1] for c in channels])
    counts = np.array([ref.n_files(c) for c in channels])
    ch_labels = [f"ch{c}" if isinstance(c, int) else c for c in channels]

    # ── 1a. Reference mean heatmap ───────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(18, 6))
    # Z-score normalise each feature column so the colour scale is comparable
    means_norm = (means - means.mean(0)) / (means.std(0) + 1e-9)
    im = ax.imshow(means_norm.T, aspect="auto", cmap=CMAP_BIPOLAR,
                   vmin=-3, vmax=3)
    ax.set_xlabel("Channel")
    ax.set_ylabel("Feature")
    ax.set_xticks(range(len(channels)))
    ax.set_xticklabels(ch_labels, fontsize=6, rotation=90)
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
    ax.set_xticklabels(ch_labels, fontsize=6, rotation=90)
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
    ax.set_xticklabels(ch_labels, fontsize=6, rotation=90)
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

    channels = _channel_order(ref.known_channels(), PSEUDO_TRIGGER, PSEUDO_LVDS)
    real_channels   = [c for c in channels if isinstance(c, int)]
    pseudo_channels = [c for c in channels if not isinstance(c, int)]
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

# Shared colour palette for per-channel alert status, used across all sub-plots.
_STATUS_RING_COLOR = {
    "alert": "tomato",
    "warn":  "gold",
    "ok":    "mediumseagreen",
}
_STATUS_BAR_COLOR = {
    "alert": "tomato",
    "warn":  "gold",
    "ok":    "steelblue",   # bars use blue for nominal so they don't dominate
}
_STATUS_BG_COLOR = {
    "alert": ("tomato", 0.12),
    "warn":  ("gold",   0.12),
    "ok":    (None,     0.0),
}


def _channel_status(
    results: "pd.DataFrame",
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
) -> dict:
    """
    Classify each channel as 'alert', 'warn', or 'ok' using the same single-file
    conditions as monitor.process_file.

    'alert' — anomalous AND (the file triggered a bulk alert because n_anomalous ≥
              single_file_alert_n_channels, OR this channel itself triggered an
              extreme alert because its max_z ≥ single_file_alert_max_z).
    'warn'  — anomalous but below both single-file alert thresholds.
    'ok'    — not anomalous.

    A threshold of 0 disables that condition; when both are 0 every anomalous
    channel becomes 'warn'.
    """
    n_bad   = int(results["anomalous"].sum())
    is_bulk = single_file_alert_n_channels > 0 and n_bad >= single_file_alert_n_channels

    status = {}
    for ch in results.index:
        if not results.loc[ch, "anomalous"]:
            status[ch] = "ok"
        else:
            max_z_val  = results.loc[ch, "max_z"]
            is_extreme = (
                single_file_alert_max_z > 0
                and not pd.isna(max_z_val)
                and float(max_z_val) >= single_file_alert_max_z
            )
            status[ch] = "alert" if (is_bulk or is_extreme) else "warn"

    return status


def plot_file(
    filepath: str,
    detector: AnomalyDetector,
    out_dir: Path,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
) -> None:
    """
    Four diagnostic figures for the anomaly analysis of one Digitizer CSV file.

    Channel severity is classified using the same single-file alert conditions as
    monitor.process_file:

        alert  — anomalous and exceeds the bulk or extreme threshold
                 (red in every sub-plot)
        warn   — anomalous but below the single-file alert thresholds
                 (yellow in every sub-plot)
        ok     — not anomalous
                 (green ring in the geometry map, blue bar in bar charts)

    Passing single_file_alert_n_channels=0 and single_file_alert_max_z=0 (the
    defaults) disables alert classification: all anomalous channels become 'warn'.
    """
    from .features import PSEUDO_TRIGGER, PSEUDO_LVDS
    from matplotlib.lines import Line2D

    stem      = Path(filepath).stem
    ref       = detector.reference
    feat_cols = ref._feat_cols

    results  = detector.analyze_file(filepath)
    features = extract_features(filepath)
    z_df     = ref.z_score(features)

    # Per-channel alert classification (used by all sub-plots)
    ch_status = _channel_status(results, single_file_alert_n_channels,
                                single_file_alert_max_z)

    # Read geometry from raw CSV (channel → row, column, layer)
    raw = pd.read_csv(filepath)
    geom = (raw.groupby("channel")[["row", "column", "layer"]]
               .first()
               .reset_index())

    # Channel ordering: integers numerically, then pseudo-channels in canonical order
    channels        = _channel_order(results.index, PSEUDO_TRIGGER, PSEUDO_LVDS)
    real_channels   = [c for c in channels if isinstance(c, int)]
    pseudo_channels = [c for c in channels if not isinstance(c, int)]
    n_ch            = len(channels)
    n_feat          = len(feat_cols)
    ch_idx          = {ch: i for i, ch in enumerate(channels)}
    ch_labels       = [f"ch{c}" if isinstance(c, int) else c for c in channels]

    # ── 2a. Z-score heatmap ──────────────────────────────────────────────────
    z_matrix = np.full((n_ch, n_feat), np.nan)
    for ch in channels:
        if ch in z_df.index and not z_df.loc[ch].isna().all():
            z_matrix[ch_idx[ch]] = np.clip(z_df.loc[ch].abs().values, 0, 50)

    cell_w = 0.50
    cell_h = 0.22
    fig_w  = max(16, n_feat * cell_w + 4.0)
    fig_h  = max( 8, n_ch   * cell_h + 2.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    cmap = plt.get_cmap(CMAP_ZSCORE).copy()
    cmap.set_bad(color="#f0f0f0")
    im = ax.imshow(z_matrix, aspect="auto", cmap=cmap, vmin=0, vmax=10,
                   interpolation="nearest")

    # Cell text (actual |z| value)
    for i in range(n_ch):
        for j in range(n_feat):
            v = z_matrix[i, j]
            if np.isnan(v):
                continue
            norm_val = min(v / 10.0, 1.0)
            text_color = "white" if norm_val > 0.65 else "black"
            ax.text(j, i, _fmt(v), ha="center", va="center",
                    fontsize=5, color=text_color, clip_on=True)

    # Row background: red for alert channels, yellow for warn, none for ok
    for ch in channels:
        bg_color, bg_alpha = _STATUS_BG_COLOR[ch_status[ch]]
        if bg_color is not None:
            ax.barh(ch_idx[ch], n_feat, left=0, height=0.95,
                    color=bg_color, alpha=bg_alpha, zorder=0)

    # Separator between real and pseudo-channels
    if pseudo_channels:
        ax.axhline(len(real_channels) - 0.5, color="steelblue", linewidth=1.5, linestyle="--")

    ax.set_xlim(-0.5, n_feat - 0.5)  # barh extends to x=n_feat; restore imshow limits
    ax.set_xticks(range(n_feat))
    ax.set_xticklabels(feat_cols, fontsize=6, rotation=45, ha="right")
    ax.set_yticks(range(n_ch))
    ax.set_yticklabels(ch_labels, fontsize=6)
    ax.set_xlabel("Feature", fontsize=8)
    ax.set_ylabel("Digitiser", fontsize=8)
    ax.set_title(f"Z-score heatmap — {stem}\n"
                 f"(clamped at 50σ;  red row = ALERT  ·  yellow = WARN)")
    fig.colorbar(im, ax=ax, label="|z-score|", shrink=0.4, pad=0.01)
    fig.tight_layout()
    _save(fig, out_dir / f"{stem}_zscore_heatmap.png")

    # ── 2b. Max |z| per channel ──────────────────────────────────────────────
    max_z      = results.loc[channels, "max_z"].fillna(0).values
    bar_colors = [_STATUS_BAR_COLOR[ch_status[ch]] for ch in channels]
    fig, ax    = plt.subplots(figsize=(14, 4))
    ax.bar(range(n_ch), max_z, color=bar_colors, width=0.8)
    threshold_line = ax.axhline(detector.z_threshold, color="black", linestyle="--",
                                linewidth=1)
    from matplotlib.patches import Patch
    from matplotlib.lines   import Line2D as _L2D
    ax.legend(
        handles=[
            _L2D([0], [0], color="black", linestyle="--", linewidth=1),
            Patch(facecolor=_STATUS_BAR_COLOR["alert"]),
            Patch(facecolor=_STATUS_BAR_COLOR["warn"]),
            Patch(facecolor=_STATUS_BAR_COLOR["ok"]),
        ],
        labels=[f"z threshold = {detector.z_threshold}σ", "ALERT", "WARN", "OK"],
        fontsize=8,
    )
    ax.set_xlabel("Channel")
    ax.set_ylabel("Max |z-score|")
    ax.set_xticks(range(n_ch))
    ax.set_xticklabels(ch_labels, fontsize=6, rotation=90)
    ax.set_title(f"Max |z-score| per channel — {stem}\n"
                 f"(red = ALERT  ·  yellow = WARN  ·  blue = OK)")
    ax.set_yscale("symlog", linthresh=10)
    fig.tight_layout()
    _save(fig, out_dir / f"{stem}_max_zscore.png")

    # ── 2c. Isolation Forest score per channel ───────────────────────────────
    if_scores = results.loc[channels, "if_score"].values
    if not np.all(np.isnan(if_scores)):
        fig, ax = plt.subplots(figsize=(14, 4))
        ax.bar(range(n_ch), if_scores, color=bar_colors, width=0.8)
        ax.set_xlabel("Channel")
        ax.set_ylabel("IF anomaly score")
        ax.set_xticks(range(n_ch))
        ax.set_xticklabels(ch_labels, fontsize=6, rotation=90)
        ax.set_title(f"Isolation Forest anomaly score per channel — {stem}\n"
                     f"(more negative = more anomalous;  red = ALERT  ·  yellow = WARN  ·  blue = OK)")
        fig.tight_layout()
        _save(fig, out_dir / f"{stem}_if_scores.png")

    # ── 2d. Detector geometry map ────────────────────────────────────────────
    geom = geom[geom["channel"].isin(channels)].copy()
    geom["max_z"]  = geom["channel"].map(results["max_z"].to_dict()).fillna(0)
    geom["status"] = geom["channel"].map(ch_status)

    layers = sorted(geom["layer"].unique())
    ncols  = len(layers)
    nrows  = 1
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(5 * ncols, 4 * nrows + 1.2),
                             squeeze=False)
    vmax = max(geom["max_z"].max(), detector.z_threshold + 1)

    for idx, layer in enumerate(layers):
        ax  = axes[idx // ncols][idx % ncols]
        sub = geom[geom["layer"] == layer].copy()

        # Two channels share each (column, row) position (paired by channel parity:
        # even channels sit at row + 0.2, odd channels at row − 0.2).
        sub["row_plot"] = sub["row"].astype(float) + sub["channel"].apply(
            lambda c: 0.2 if c % 2 == 0 else -0.2
        )

        sc  = ax.scatter(sub["column"], sub["row_plot"],
                         c=sub["max_z"].clip(0, vmax),
                         cmap=CMAP_ZSCORE, vmin=0, vmax=vmax,
                         s=200, edgecolors="black", linewidths=0.4, zorder=3)
        # Draw one ring per channel, coloured by alert status.
        # Draw ok first (bottom), then warn, then alert on top.
        for ring_status, ring_size, ring_lw in [
            ("ok",    270, 1.6),
            ("warn",  310, 3.0),
            ("alert", 340, 4.0),
        ]:
            group = sub[sub["status"] == ring_status]
            if not group.empty:
                ax.scatter(group["column"], group["row_plot"],
                           s=ring_size, facecolors="none",
                           edgecolors=_STATUS_RING_COLOR[ring_status],
                           linewidths=ring_lw,
                           zorder=4 + ["ok", "warn", "alert"].index(ring_status))
        ax.set_xticks(sorted(sub["column"].unique()))
        ax.set_yticks(sorted(sub["row"].unique()))
        ax.set_title(f"Layer {layer}")
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        # row 1 at the bottom — no y-axis inversion
        fig.colorbar(sc, ax=ax, label="|z|")

    # Hide unused axes
    for idx in range(len(layers), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    # Shared ring-colour legend at the bottom of the figure
    legend_elems = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
               markeredgecolor=_STATUS_RING_COLOR["ok"],    markeredgewidth=1.6,
               markersize=10, label="OK"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
               markeredgecolor=_STATUS_RING_COLOR["warn"],  markeredgewidth=3.0,
               markersize=10, label="WARN"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none",
               markeredgecolor=_STATUS_RING_COLOR["alert"], markeredgewidth=4.0,
               markersize=10, label="ALERT"),
    ]
    fig.legend(handles=legend_elems, loc="lower center", ncol=3,
               fontsize=8, framealpha=0.85, bbox_to_anchor=(0.5, 0.0))

    fig.suptitle(f"Detector geometry map — {stem}\n"
                 f"(colour = max |z|  ·  green ring = OK  ·  yellow = WARN  ·  red = ALERT)",
                 y=1.01)
    fig.tight_layout(rect=[0, 0.06, 1, 1])
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


def _compute_persistence_status(
    df: "pd.DataFrame",
    file_alert_n_channels: int,
    alert_consecutive_n: int,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
) -> "pd.DataFrame":
    """
    Replay the anomaly log in run/subrun order and compute the alert status for
    every file, mirroring the full alert logic in monitor.process_file.

    Three independent conditions can raise 'alert':
      1. Persistent  — n_persistent >= file_alert_n_channels
      2. Bulk        — n_anomalous  >= single_file_alert_n_channels (0 = disabled)
      3. Extreme     — any anomalous channel's max_z >= single_file_alert_max_z
                       (0.0 = disabled)

    Status values returned:
        'alert' — any alert condition fired
        'warn'  — anomalous channels present but no alert condition met
        'pend'  — first alert_consecutive_n-1 files of a run, no anomalies
                  (not yet enough within-run history to confirm nominal)
        'ok'    — nominal and past the probationary window
    """
    from collections import deque

    files_sorted = sorted(df["filename"].unique(), key=_run_subrun_key)

    # Pre-build per-file channel sets and per-file worst anomalous max_z from log
    anom_sets:    dict = {}
    all_sets:     dict = {}
    file_max_z:   dict = {}   # fname → max max_z among anomalous channels
    for fname, grp in df.groupby("filename"):
        anom_grp           = grp[grp["anomalous"]]
        anom_sets[fname]   = set(anom_grp["channel"])
        all_sets[fname]    = set(grp["channel"])
        valid_z            = anom_grp["max_z"].dropna()
        file_max_z[fname]  = float(valid_z.max()) if not valid_z.empty else 0.0

    channel_history: dict      = {}
    current_run:     object    = None   # reset history at run boundaries
    run_file_index:  int       = 0
    rows = []

    for fname in files_sorted:
        run_k, sub_k = _run_subrun_key(fname)

        # Reset channel history when the run number changes, so that
        # the persistence window never spans two different runs.
        if run_k != current_run:
            current_run     = run_k
            run_file_index  = 0
            channel_history = {}

        anom_chs = anom_sets.get(fname, set())
        all_chs  = all_sets.get(fname, set())
        n_bad    = len(anom_chs)

        n_persistent = 0
        n_transient  = 0

        for ch in anom_chs:
            if alert_consecutive_n > 1:
                hist = channel_history.get(ch, deque())
                if len(hist) >= alert_consecutive_n - 1 and all(hist):
                    n_persistent += 1
                else:
                    n_transient += 1
            else:
                n_persistent += 1

        if alert_consecutive_n > 1:
            for ch in all_chs:
                if ch not in channel_history:
                    channel_history[ch] = deque(maxlen=alert_consecutive_n - 1)
                channel_history[ch].append(ch in anom_chs)

        # Single-file alert conditions (mirror monitor.process_file)
        is_bulk    = single_file_alert_n_channels > 0 and n_bad >= single_file_alert_n_channels
        is_extreme = single_file_alert_max_z > 0 and file_max_z.get(fname, 0.0) >= single_file_alert_max_z

        # Probationary files (first alert_consecutive_n-1 of each run) cannot
        # be "ok" — label them "pend" to match the monitor's [PEND] output.
        n_probationary = max(0, alert_consecutive_n - 1)
        if n_persistent >= file_alert_n_channels or is_bulk or is_extreme:
            status = "alert"
        elif n_persistent + n_transient > 0:
            status = "warn"
        elif run_file_index < n_probationary:
            status = "pend"
        else:
            status = "ok"

        run_file_index += 1

        rows.append({
            "filename":     fname,
            "run":          run_k if run_k != float("inf") else None,
            "subrun":       sub_k if sub_k != float("inf") else None,
            "n_anomalous":  n_bad,
            "n_persistent": n_persistent,
            "n_transient":  n_transient,
            "status":       status,
        })

    return pd.DataFrame(rows)


def plot_log(
    log_path: str,
    out_dir: Path,
    file_alert_n_channels: int = 2,
    alert_consecutive_n: int = 1,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
) -> None:
    """Six figures summarising the anomaly log (four raw-count plots + two persistence plots)."""
    df = pd.read_csv(log_path)
    if df.empty:
        print("ERROR: Log file is empty.", file=sys.stderr)
        return

    # Compute persistence-aware status once; shared by plots 3a, 3d, 3e, 3f.
    status_df = _compute_persistence_status(
        df, file_alert_n_channels, alert_consecutive_n,
        single_file_alert_n_channels=single_file_alert_n_channels,
        single_file_alert_max_z=single_file_alert_max_z,
    )
    # Build a filename → status lookup for the bar-chart plots
    file_status = status_df.set_index("filename")["status"].to_dict()

    # ── 3a. Anomalous channel count per file ─────────────────────────────────
    per_file = (df.groupby("filename")
                  .agg(total=("channel", "count"),
                       n_anomalous=("anomalous", "sum"))
                  .reset_index())

    # Sort by run number then subrun number
    per_file["_sort_key"] = per_file["filename"].apply(_run_subrun_key)
    per_file = per_file.sort_values("_sort_key").drop(columns="_sort_key").reset_index(drop=True)

    # Colour bars using the full alert status (persistence + bulk + extreme)
    _STATUS_BAR_3A = {"alert": "tomato", "warn": "darkorange",
                      "pend": "lightsteelblue", "ok": "steelblue"}
    colors = [_STATUS_BAR_3A.get(file_status.get(fn, "ok"), "steelblue")
              for fn in per_file["filename"]]

    n_files = len(per_file)
    # Cap width to avoid matplotlib's 2^16 pixel limit at 150 DPI (~436 inches).
    # Above 150 files the x-labels become unreadable anyway, so drop them.
    LABEL_THRESHOLD = 150
    fig_w = min(max(8, n_files * 0.5), 80)
    fig, ax = plt.subplots(figsize=(fig_w, 4))
    ax.bar(range(n_files), per_file["n_anomalous"], color=colors, width=0.8)
    ax.axhline(file_alert_n_channels, color="black", linestyle="--", linewidth=1,
               label=f"persistent alert threshold ({file_alert_n_channels} ch)")
    if single_file_alert_n_channels > 0:
        ax.axhline(single_file_alert_n_channels, color="grey", linestyle=":",
                   linewidth=1, label=f"bulk alert threshold ({single_file_alert_n_channels} ch)")
    ax.set_ylabel("Anomalous channels (count)")
    if n_files <= LABEL_THRESHOLD:
        ax.set_xticks(range(n_files))
        ax.set_xticklabels(
            ["● " + fn for fn in per_file["filename"]],
            fontsize=6, rotation=45, ha="right",
        )
        for tick, c in zip(ax.get_xticklabels(), colors):
            tick.set_color(c)
        ax.set_xlabel("File (sorted by run / subrun)")
    else:
        ax.set_xticks([])
        ax.set_xlabel(f"File (sorted by run / subrun) — {n_files} files, labels hidden above {LABEL_THRESHOLD}")
    ax.set_title("Anomalous channel count per file\n"
                 "(red = ALERT · orange = WARN · light blue = PEND · blue = OK)")
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
                   .astype(str)
                   .str.split(";")
                   .explode()
                   .str.strip())
    triggered = triggered[(triggered != "") & (triggered != "nan")]
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

    # ── 3d. Per-run good-subrun fraction (raw, non-persistence-aware) ─────────
    per_file["_run"]    = per_file["filename"].apply(lambda f: _run_subrun_key(f)[0])
    per_file["_subrun"] = per_file["filename"].apply(lambda f: _run_subrun_key(f)[1])
    per_file["_status"] = per_file["filename"].map(file_status).fillna("ok")
    parseable = per_file[per_file["_run"] != float("inf")].copy()

    if parseable.empty:
        print("  No parseable run/subrun filenames — skipping run summary plot.")
    else:
        # 'good' = ok only; 'pend' is uncertain; 'warn'/'alert' are not good
        parseable["is_good"] = parseable["_status"] == "ok"
        parseable["is_pend"] = parseable["_status"] == "pend"
        run_stats = (
            parseable.groupby("_run")
                     .agg(n_subruns=("filename",  "count"),
                          n_good   =("is_good",   "sum"),
                          n_pend   =("is_pend",   "sum"))
                     .assign(pct_good=lambda x: x["n_good"] / x["n_subruns"] * 100)
                     .reset_index()
                     .sort_values("_run")
        )

        n_runs = len(run_stats)
        fig_w  = max(8, n_runs * 1.0)
        fig, ax = plt.subplots(figsize=(fig_w, 4))
        bar_colors = [
            "steelblue"      if r.n_good == r.n_subruns else
            ("lightsteelblue" if r.n_good + r.n_pend == r.n_subruns else
             ("tomato"        if r.n_good == 0 and r.n_pend == 0 else "darkorange"))
            for r in run_stats.itertuples()
        ]
        ax.bar(range(n_runs), run_stats["pct_good"],
               color=bar_colors, width=0.6, edgecolor="white", linewidth=0.5)

        # Annotate each bar with "good[+pending]/total"
        for i, row in enumerate(run_stats.itertuples()):
            label = (f"{int(row.n_good)}/{int(row.n_subruns)}"
                     if row.n_pend == 0 else
                     f"{int(row.n_good)}+{int(row.n_pend)}p/{int(row.n_subruns)}")
            ax.text(i, min(row.pct_good + 2, 103), label,
                    ha="center", va="bottom", fontsize=7)

        ax.set_xlim(-0.5, n_runs - 0.5)
        ax.set_ylim(0, 115)
        ax.set_ylabel("OK subruns (%)")
        ax.set_xticks(range(n_runs))
        ax.set_xticklabels(
            ["● " + f"run{int(r)}" for r in run_stats["_run"]],
            rotation=45, ha="right", fontsize=8,
        )
        for tick, c in zip(ax.get_xticklabels(), bar_colors):
            tick.set_color(c)
        ax.axhline(100, color="steelblue", linestyle=":", linewidth=0.8, alpha=0.5)
        ax.set_title(
            f"Subrun quality per run  (alert threshold: {file_alert_n_channels} anomalous ch,"
            + (f" bulk ≥{single_file_alert_n_channels}" if single_file_alert_n_channels else "")
            + (f", extreme z≥{single_file_alert_max_z}" if single_file_alert_max_z else "")
            + ")\nblue = all OK · light blue = unconfirmed (PEND) · orange = partial · red = all ALERT"
        )
        fig.tight_layout()
        _save(fig, out_dir / "log_run_summary.png")

    # ── 3e & 3f. Persistence-aware subrun grid and run summary ───────────────
    # status_df already computed at the top of this function
    _plot_persistence_subrun_grid(status_df, out_dir, alert_consecutive_n,
                                  file_alert_n_channels, single_file_alert_n_channels,
                                  single_file_alert_max_z)
    _plot_persistence_run_summary(status_df, out_dir, alert_consecutive_n,
                                  file_alert_n_channels, single_file_alert_n_channels,
                                  single_file_alert_max_z)

    print(f"  Log plots saved to {out_dir}/")


# ══════════════════════════════════════════════════════════════════════════════
# 4.  PERSISTENCE-AWARE PLOTS  (called from plot_log)
# ══════════════════════════════════════════════════════════════════════════════

# Status colour palette shared by both persistence plots.
# "pend" = first files of a run, no anomalies but not yet confirmed nominal.
_PERSIST_COLORS = {
    "ok":      "steelblue",
    "pend":    "lightsteelblue",
    "warn":    "darkorange",
    "alert":   "tomato",
    "no data": "#d0d0d0",
}


def _plot_persistence_subrun_grid(
    status_df: "pd.DataFrame",
    out_dir: Path,
    alert_consecutive_n: int,
    file_alert_n_channels: int,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
) -> None:
    """
    Heatmap grid: rows = run numbers, columns = subrun numbers.
    Each cell is coloured by its persistence-aware status.
    Saved as log_persistence_subrun_grid.png.
    """
    parseable = status_df.dropna(subset=["run", "subrun"]).copy()
    if parseable.empty:
        print("  No parseable run/subrun filenames — skipping persistence subrun grid.")
        return

    parseable["run"]    = parseable["run"].astype(int)
    parseable["subrun"] = parseable["subrun"].astype(int)

    runs    = sorted(parseable["run"].unique())
    subruns = sorted(parseable["subrun"].unique())
    n_runs  = len(runs)
    n_subs  = len(subruns)

    # Integer code matrix: 0=no data, 1=ok, 2=pend, 3=warn, 4=alert
    code_map = {"ok": 1, "pend": 2, "warn": 3, "alert": 4}
    run_idx  = {r: i for i, r in enumerate(runs)}
    sub_idx  = {s: i for i, s in enumerate(subruns)}

    grid = np.zeros((n_runs, n_subs), dtype=int)
    for _, row in parseable.iterrows():
        grid[run_idx[row["run"]], sub_idx[row["subrun"]]] = code_map.get(row["status"], 0)

    cell_h = max(0.22, min(0.45, 14.0 / n_runs))
    cell_w = max(0.22, min(0.45, 20.0 / n_subs))
    fig_h  = max(4, n_runs * cell_h + 2.5)
    fig_w  = max(6, n_subs * cell_w + 3.5)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    cmap  = mcolors.ListedColormap([
        _PERSIST_COLORS["no data"],
        _PERSIST_COLORS["ok"],
        _PERSIST_COLORS["pend"],
        _PERSIST_COLORS["warn"],
        _PERSIST_COLORS["alert"],
    ])
    norm  = mcolors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5, 4.5], cmap.N)

    ax.imshow(grid, aspect="auto", cmap=cmap, norm=norm, interpolation="nearest")

    ax.set_yticks(range(n_runs))
    ax.set_yticklabels([f"run{r}" for r in runs], fontsize=7)
    ax.set_xticks(range(n_subs))
    ax.set_xticklabels([f"sr{s}" for s in subruns], fontsize=7, rotation=45, ha="right")
    ax.set_xlabel("Subrun", fontsize=8)
    ax.set_ylabel("Run", fontsize=8)
    alert_conditions = f"{file_alert_n_channels} persistent ch"
    if single_file_alert_n_channels:
        alert_conditions += f" / bulk ≥{single_file_alert_n_channels} ch"
    if single_file_alert_max_z:
        alert_conditions += f" / extreme z≥{single_file_alert_max_z}"
    ax.set_title(
        f"Subrun status — window: {alert_consecutive_n} consecutive file(s),"
        f" ALERT if: {alert_conditions}\n"
        f"blue = OK · light blue = PEND (run start) · orange = WARN"
        f" · red = ALERT · grey = no data",
        fontsize=9,
    )

    # Discrete colorbar legend
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor=_PERSIST_COLORS["ok"],      label="OK"),
        Patch(facecolor=_PERSIST_COLORS["pend"],    label="PEND — run start, unconfirmed"),
        Patch(facecolor=_PERSIST_COLORS["warn"],    label="WARN — transient anomaly"),
        Patch(facecolor=_PERSIST_COLORS["alert"],   label="ALERT — persistent / bulk / extreme"),
        Patch(facecolor=_PERSIST_COLORS["no data"], label="no data"),
    ]
    ax.legend(handles=legend_elems, loc="upper right", fontsize=7,
              framealpha=0.85, bbox_to_anchor=(1.0, 1.0))

    fig.tight_layout()
    _save(fig, out_dir / "log_persistence_subrun_grid.png")


def _plot_persistence_run_summary(
    status_df: "pd.DataFrame",
    out_dir: Path,
    alert_consecutive_n: int,
    file_alert_n_channels: int,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
) -> None:
    """
    Bar chart of run quality using persistence-aware subrun classification.
    A subrun is 'bad' when its status is 'alert' (persistent, bulk, or extreme).
    Saved as log_persistence_run_summary.png.
    """
    parseable = status_df.dropna(subset=["run", "subrun"]).copy()
    if parseable.empty:
        print("  No parseable run/subrun filenames — skipping persistence run summary.")
        return

    parseable["run"]    = parseable["run"].astype(int)
    parseable["subrun"] = parseable["subrun"].astype(int)
    parseable["is_bad"]  = parseable["status"] == "alert"
    parseable["is_pend"] = parseable["status"] == "pend"

    run_stats = (
        parseable.groupby("run")
                 .agg(n_subruns=("filename", "count"),
                      n_bad=("is_bad", "sum"),
                      n_pend=("is_pend", "sum"))
                 .assign(n_good=lambda x: x["n_subruns"] - x["n_bad"] - x["n_pend"],
                         pct_good=lambda x: (1 - x["n_bad"] / x["n_subruns"]) * 100)
                 .reset_index()
                 .sort_values("run")
    )

    n_runs = len(run_stats)
    fig_w  = max(8, n_runs * 1.0)
    fig, ax = plt.subplots(figsize=(fig_w, 4))

    def _bar_color(row):
        if row.n_bad > 0:
            return _PERSIST_COLORS["alert"] if row.pct_good == 0 else _PERSIST_COLORS["warn"]
        if row.n_pend > 0:
            # All non-bad subruns are pending: run start not yet confirmed
            return _PERSIST_COLORS["pend"]
        return _PERSIST_COLORS["ok"]

    bar_colors = [_bar_color(row) for row in run_stats.itertuples()]

    ax.bar(range(n_runs), run_stats["pct_good"],
           color=bar_colors, width=0.6, edgecolor="white", linewidth=0.5)

    for i, row in enumerate(run_stats.itertuples()):
        label = (f"{int(row.n_good)}/{int(row.n_subruns)}"
                 if row.n_pend == 0 else
                 f"{int(row.n_good)}+{int(row.n_pend)}p/{int(row.n_subruns)}")
        ax.text(i, min(row.pct_good + 2, 103), label,
                ha="center", va="bottom", fontsize=7)

    ax.set_xlim(-0.5, n_runs - 0.5)
    ax.set_ylim(0, 115)
    ax.set_ylabel("Non-ALERT subruns (%)", fontsize=9)
    ax.set_xticks(range(n_runs))
    ax.set_xticklabels(
        ["● " + f"run{int(r)}" for r in run_stats["run"]],
        rotation=45, ha="right", fontsize=8,
    )
    for tick, c in zip(ax.get_xticklabels(), bar_colors):
        tick.set_color(c)
    ax.axhline(100, color=_PERSIST_COLORS["ok"], linestyle=":", linewidth=0.8, alpha=0.5)
    alert_conditions = f"{file_alert_n_channels} persistent ch"
    if single_file_alert_n_channels:
        alert_conditions += f" / bulk ≥{single_file_alert_n_channels} ch"
    if single_file_alert_max_z:
        alert_conditions += f" / extreme z≥{single_file_alert_max_z}"
    ax.set_title(
        f"Run quality — window: {alert_consecutive_n} consecutive file(s),"
        f" ALERT if: {alert_conditions}\n"
        f"blue = all OK · light blue = unconfirmed (PEND) · orange = partial · red = all ALERT",
        fontsize=9,
    )
    fig.tight_layout()
    _save(fig, out_dir / "log_persistence_run_summary.png")


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
    _, cfg = preparse_config()

    tag = cfg["model_tag"]

    parser = argparse.ArgumentParser(
        description="Generate visualizations for training and anomaly detection output."
    )
    add_config(parser)
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
    p_file.add_argument("--single-file-alert-n-channels", type=int,
                        default=cfg["single_file_alert_n_channels"],
                        help="Bulk alert threshold: N or more anomalous channels → ALERT ring (0 = disabled)")
    p_file.add_argument("--single-file-alert-max-z", type=float,
                        default=cfg["single_file_alert_max_z"],
                        help="Extreme alert threshold: max_z ≥ Z → ALERT ring (0 = disabled)")

    p_log = sub.add_parser("log", help="Plot summary of the anomaly log")
    p_log.add_argument("--log-file",
                       default=str(Path(cfg["logs_dir"]) / f"{tag}.csv"),
                       help="Path to the anomaly log CSV")
    p_log.add_argument("--file-alert-n-channels", type=int,
                       default=cfg["file_alert_n_channels"],
                       help="Number of persistent anomalous channels that marks a file as ALERT")
    p_log.add_argument("--alert-consecutive-n", type=int,
                       default=cfg["alert_consecutive_n"],
                       help="Consecutive files a channel must be anomalous in to count as persistent")
    p_log.add_argument("--single-file-alert-n-channels", type=int,
                       default=cfg["single_file_alert_n_channels"],
                       help="Bulk alert threshold passed to status classification (0 = disabled)")
    p_log.add_argument("--single-file-alert-max-z", type=float,
                       default=cfg["single_file_alert_max_z"],
                       help="Extreme alert threshold passed to status classification (0 = disabled)")

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
        plot_file(args.csv, detector, out_dir,
                  single_file_alert_n_channels=args.single_file_alert_n_channels,
                  single_file_alert_max_z=args.single_file_alert_max_z)

    elif args.command == "log":
        if not Path(args.log_file).exists():
            print(f"ERROR: Log file not found: {args.log_file}", file=sys.stderr)
            sys.exit(1)
        plot_log(args.log_file, out_dir,
                 file_alert_n_channels=args.file_alert_n_channels,
                 alert_consecutive_n=args.alert_consecutive_n,
                 single_file_alert_n_channels=args.single_file_alert_n_channels,
                 single_file_alert_max_z=args.single_file_alert_max_z)


if __name__ == "__main__":
    main()
