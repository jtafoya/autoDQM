"""
Visualization for training and anomaly detection output.

Subcommands:
    python3 -m src.plot reference              — reference model statistics
    python3 -m src.plot file <csv_path>        — per-channel anomaly analysis of one file
    python3 -m src.plot log [--log-file ...]   — summary of the anomaly log over time

All figures are saved to --out-dir (default: plots/).  The output format is
controlled by --plot-format (png / pdf / svg; default: png).  Pass --plot-format pdf
to produce vector figures suitable for publication or lossless zooming.

All public plot functions accept a ``fmt`` keyword argument (default "png") that
is forwarded to the internal ``_save`` helper, which replaces the path suffix
automatically — callers always construct paths with a .png extension and the
actual extension is substituted at save time.

The eval confusion plot (eval_confusion.<fmt>) is generated here from the
eval_confusion_data.json written by the evaluate step, so that --skip-all-plots
suppresses it consistently with every other plot.

Public API
----------
step_plots(log_file, models_dir, plots_dir, ...)
    Pipeline step called by pipeline.py: auto-skip guard + all plot generation.
plot_reference(ref, out_dir, fmt)  — reference model statistics
plot_file(filepath, detector, out_dir, ...)  — per-file anomaly diagnostics
plot_config_state(filepath, detector, out_dir, fmt)
    Three additional diagnostic figures generated automatically by plot_file when
    include_trigger_config=True:

    {stem}_config_trigger.{fmt}
        Raw vs prescale-normalised trigger rates for trigger types 1–13.
        Side-by-side bars show the effect of prescale normalisation; grey bars
        indicate trigger types disabled by triggerBoard.trigger.  The prescale
        factor is annotated above each enabled bar.

    {stem}_config_zscore_comparison.{fmt}
        Side-by-side |z|-score heatmaps for ALL channels and features:
        left = raw features (no config), right = config-normalised (model input).
        Grey cells in the right panel = masked channels or disabled triggers
        correctly excluded from scoring.  Cells with lower |z| on the right are
        false positives that config integration suppresses.

    {stem}_config_mask.{fmt}
        Detector geometry (one panel per layer) showing which channels were
        silenced by triggerBoard.trigger_mask.  Grey × = masked (all features
        NaN'd, excluded from reference and scoring); coloured dots = active
        channels, coloured red/blue by anomaly status.
plot_log(log_path, out_dir, ...)  — anomaly log summary
plot_eval_confusion(confusion_data_path, plots_dir, fmt)  — confusion bar chart
"""

import argparse
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless — no display needed
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

from .args import preparse_config, add_config, add_plot_format
from .config import print_step_header
from .reference import ReferenceModel
from .detector import AnomalyDetector
from .features import extract_features, METRIC_COLS
from .run_list import run_subrun_sort_key

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

def plot_reference(ref: ReferenceModel, out_dir: Path, fmt: str = "png") -> None:
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
    _save(fig, out_dir / "reference_means.png", fmt)

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
    _save(fig, out_dir / "reference_stds.png", fmt)

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
    _save(fig, out_dir / "reference_coverage.png", fmt)

    print(f"  Reference plots saved to {out_dir}/")


def plot_mean_table(ref: ReferenceModel, out_dir: Path, fmt: str = "png") -> None:
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
    _save(fig, out_dir / "reference_mean_table.png", fmt)


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
    fmt: str = "png",
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
    # Extract with the same config flags the detector uses so that z-scores shown
    # in the heatmap match what the detector actually computed (masked channels
    # and disabled triggers appear as NaN rather than potentially misleading values).
    features = extract_features(
        filepath,
        use_trigger=detector._use_trigger,
        use_lvds=detector._use_lvds,
        ignore_features=detector._ignore_features,
        include_trigger_config=detector._include_trigger_config,
        trigger_config_vars=detector._trigger_config_vars,
        include_daq_config=detector._include_daq_config,
        daq_config_vars=detector._daq_config_vars,
        run_configs_dir=detector._run_configs_dir,
        thresholds_json_path=detector._thresholds_json_path,
    )
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
    _save(fig, out_dir / f"{stem}_zscore_heatmap.png", fmt)

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
    _save(fig, out_dir / f"{stem}_max_zscore.png", fmt)

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
        _save(fig, out_dir / f"{stem}_if_scores.png", fmt)

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
    _save(fig, out_dir / f"{stem}_geometry.png", fmt)

    # ── 2e & 2f. Config state (only when trigger config integration is active) ─
    if detector._include_trigger_config:
        plot_config_state(filepath, detector, out_dir, fmt=fmt)

    print(f"  File plots saved to {out_dir}/")


# ══════════════════════════════════════════════════════════════════════════════
# 2e–f.  CONFIG STATE PLOTS  (called from plot_file when trigger config active)
# ══════════════════════════════════════════════════════════════════════════════

def plot_config_state(
    filepath: str,
    detector: AnomalyDetector,
    out_dir: Path,
    fmt: str = "png",
) -> None:
    """
    Three diagnostic figures showing the effect of config-driven normalisations
    for one Digitizer file.  Called automatically by plot_file when
    include_trigger_config=True; silently returns otherwise.

    {stem}_config_trigger.{fmt}  (when use_trigger=True and TriggerBoard file found)
        Side-by-side bars for each trigger type (bit 1–13):
          blue  = raw trigger rate from TriggerBoard CSV
          orange = prescale-normalised rate (what the model sees)
          grey  = trigger type disabled by triggerBoard.trigger
        The prescale factor is annotated above each enabled bar.
        An absent TriggerBoard file produces a "no data" note and no bars.

    {stem}_config_zscore_comparison.{fmt}
        Side-by-side |z|-score heatmaps for ALL channels and features:
          left  panel — raw features scored against the reference (no normalisation)
          right panel — config-normalised features (what the model actually uses)
        NaN cells (grey) in the right panel = masked channels or disabled triggers,
        correctly excluded from scoring.  Large z-scores that appear only in the
        left panel are false positives that config normalisation suppresses.

    {stem}_config_mask.{fmt}  (when triggerBoard.trigger_mask is in trigger_config_vars
                               and at least one channel is masked in this file)
        Detector geometry (one panel per layer) with masked and active channels:
          grey ×  = masked by trigger_mask (all features NaN'd, not scored)
          blue ●  = active and nominal
          red  ●  = active and anomalous
    """
    if not detector._include_trigger_config:
        return

    from .features import (PSEUDO_TRIGGER, TRIGGER_COLS, extract_features,
                           _DIGI_COLS, _DIGI_RE)
    from .run_config import parse_trigger_config

    stem = Path(filepath).stem
    ref  = detector.reference

    # Extract raw features (no config normalisation) for comparison baseline.
    feats_raw = extract_features(
        filepath,
        use_trigger=detector._use_trigger,
        use_lvds=detector._use_lvds,
        ignore_features=detector._ignore_features,
        include_trigger_config=False,
    )
    # Config-normalised features (what the model actually sees).
    feats_norm = extract_features(
        filepath,
        use_trigger=detector._use_trigger,
        use_lvds=detector._use_lvds,
        ignore_features=detector._ignore_features,
        include_trigger_config=True,
        trigger_config_vars=detector._trigger_config_vars,
        include_daq_config=detector._include_daq_config,
        daq_config_vars=detector._daq_config_vars,
        run_configs_dir=detector._run_configs_dir,
        thresholds_json_path=detector._thresholds_json_path,
    )

    results = detector.analyze_file(filepath)

    # ── Identify masked channels ───────────────────────────────────────────────
    # A channel is masked if it had real digitizer data in the raw extraction but
    # all digitizer features are NaN after config normalisation.
    digi_cols    = [c for c in _DIGI_COLS if c in ref._feat_cols]
    real_channels = sorted([c for c in feats_norm.index if isinstance(c, int)])

    masked_channels: set = set()
    for ch in real_channels:
        if ch not in feats_raw.index:
            continue
        raw_has_data  = not feats_raw.loc[ch, digi_cols].isna().all()
        norm_all_nan  = feats_norm.loc[ch, digi_cols].isna().all() if ch in feats_norm.index else True
        if raw_has_data and norm_all_nan:
            masked_channels.add(ch)

    # ── Parse prescale values for annotation ──────────────────────────────────
    prescales: list = [np.nan] * 16
    m = _DIGI_RE.search(Path(filepath).name)
    if m and detector._run_configs_dir and "triggerBoard.prescale" in detector._trigger_config_vars:
        run_num   = int(m.group(1))
        trig_cfg  = parse_trigger_config(run_num, detector._run_configs_dir,
                                         list(detector._trigger_config_vars))
        if trig_cfg:
            prescales = [trig_cfg.get(f"cfg_prescale_bit{i}", np.nan) for i in range(16)]

    # ── 2e. Trigger rate: raw vs normalised ───────────────────────────────────
    if detector._use_trigger:
        bit_nums  = list(range(1, 17))
        raw_vals  = []
        norm_vals = []
        tb_present = PSEUDO_TRIGGER in feats_raw.index

        for b in bit_nums:
            col = f"triggerRate_bit{b}"
            rv = float(feats_raw.loc[PSEUDO_TRIGGER, col]) \
                 if (tb_present and col in feats_raw.columns) else np.nan
            nv = float(feats_norm.loc[PSEUDO_TRIGGER, col]) \
                 if (PSEUDO_TRIGGER in feats_norm.index and col in feats_norm.columns) else np.nan
            raw_vals.append(rv)
            norm_vals.append(nv)

        fig, ax = plt.subplots(figsize=(12, 5))

        if not tb_present or all(np.isnan(v) for v in raw_vals):
            ax.text(0.5, 0.5, "No TriggerBoard data for this subrun",
                    ha="center", va="center", transform=ax.transAxes, fontsize=12, color="grey")
        else:
            width = 0.35
            raw_legend  = True
            norm_legend = True

            for i, (b, rv, nv) in enumerate(zip(bit_nums, raw_vals, norm_vals)):
                ps = prescales[i] if i < len(prescales) else np.nan

                if np.isnan(rv) and np.isnan(nv):
                    # Disabled trigger: shade the column background instead of a bar
                    # (a bar at an arbitrary height is misleading on a log scale).
                    ax.axvspan(i - 0.5, i + 0.5, color="#dddddd", alpha=0.7, zorder=0)
                else:
                    if not np.isnan(rv) and rv > 0:
                        ax.bar(i - width / 2, rv, width=width, color="steelblue", alpha=0.75,
                               label="Raw rate" if raw_legend else "_nolegend_")
                        raw_legend = False
                    if not np.isnan(nv) and nv > 0:
                        ax.bar(i + width / 2, nv, width=width, color="darkorange", alpha=0.9,
                               label="Normalised rate (model input)" if norm_legend else "_nolegend_")
                        norm_legend = False
                    # Annotate prescale factor above the taller bar.
                    # On a log scale, multiply by a fixed factor (×5) for vertical clearance.
                    if not np.isnan(ps) and ps != 1.0:
                        pos_vals = [v for v in [rv, nv] if not np.isnan(v) and v > 0]
                        if pos_vals:
                            ax.text(i, max(pos_vals) * 5, f"÷{ps:g}", ha="center", va="bottom",
                                    fontsize=7, color="dimgrey")

            ax.set_yscale("log")

        # Build x-tick labels; mark disabled types with "(off)".
        xticklabels = []
        for i, b in enumerate(bit_nums):
            rv, nv = raw_vals[i] if tb_present else np.nan, norm_vals[i]
            if np.isnan(rv) and np.isnan(nv):
                xticklabels.append(f"bit {b}\n(off)")
            else:
                xticklabels.append(f"bit {b}")

        ax.set_xticks(np.arange(len(bit_nums)))
        ax.set_xticklabels(xticklabels, fontsize=8)
        ax.set_xlabel("Trigger type")
        ax.set_ylabel("Rate  [log scale]")
        ax.set_title(
            f"Trigger rate: raw vs prescale-normalised — {stem}\n"
            f"(grey shading = disabled by triggerBoard.trigger;  ÷N = prescale factor)"
        )
        if not (not tb_present or all(np.isnan(v) for v in raw_vals)):
            ax.legend(fontsize=9)
        fig.tight_layout()
        _save(fig, out_dir / f"{stem}_config_trigger.png", fmt)

    # ── 2f. Z-score comparison: raw vs config-normalised ─────────────────────
    # Score both raw and normalised feature sets against the same reference so
    # that cells which change are visually obvious.  The left panel shows what
    # the model would see WITHOUT config integration (potential false positives);
    # the right panel shows the correctly normalised input.
    from .features import PSEUDO_LVDS as _PSEUDO_LVDS
    z_raw  = ref.z_score(feats_raw)
    z_norm = ref.z_score(feats_norm)

    _all_channels = sorted(
        set(z_raw.index) | set(z_norm.index),
        key=lambda c: (1 if isinstance(c, int) else 2, c if isinstance(c, int) else 0, str(c)),
    )
    # Canonical pseudo-channel ordering at the bottom
    _all_channels = (
        [c for c in _all_channels if isinstance(c, int)]
        + [c for c in [PSEUDO_TRIGGER, _PSEUDO_LVDS] if c in _all_channels]
    )

    feat_cols_cmp = ref._feat_cols
    n_ch_cmp      = len(_all_channels)
    n_feat_cmp    = len(feat_cols_cmp)
    ch_idx_cmp    = {ch: i for i, ch in enumerate(_all_channels)}
    ch_labels_cmp = [f"ch{c}" if isinstance(c, int) else c for c in _all_channels]

    z_raw_mat  = np.full((n_ch_cmp, n_feat_cmp), np.nan)
    z_norm_mat = np.full((n_ch_cmp, n_feat_cmp), np.nan)
    for ch in _all_channels:
        i = ch_idx_cmp[ch]
        if ch in z_raw.index and not z_raw.loc[ch].isna().all():
            z_raw_mat[i]  = np.clip(z_raw.loc[ch].abs().values, 0, 50)
        if ch in z_norm.index and not z_norm.loc[ch].isna().all():
            z_norm_mat[i] = np.clip(z_norm.loc[ch].abs().values, 0, 50)

    cell_w_cmp = 0.50
    cell_h_cmp = 0.22
    # Two side-by-side heatmaps; share y-axis
    fig_w_cmp = max(24, n_feat_cmp * cell_w_cmp * 2 + 6.0)
    fig_h_cmp = max(8,  n_ch_cmp   * cell_h_cmp + 3.0)
    cmap_cmp  = plt.get_cmap(CMAP_ZSCORE).copy()
    cmap_cmp.set_bad(color="#f0f0f0")

    fig, (ax_l, ax_r) = plt.subplots(
        1, 2, figsize=(fig_w_cmp, fig_h_cmp), sharey=True,
        gridspec_kw={"wspace": 0.04},
    )

    for ax, z_mat, panel_title in [
        (ax_l, z_raw_mat,  "Raw (no config normalisation)"),
        (ax_r, z_norm_mat, "Config-normalised  (model input)"),
    ]:
        im = ax.imshow(z_mat, aspect="auto", cmap=cmap_cmp, vmin=0, vmax=10,
                       interpolation="nearest")
        for i in range(n_ch_cmp):
            for j in range(n_feat_cmp):
                v = z_mat[i, j]
                if np.isnan(v):
                    continue
                norm_v = min(v / 10.0, 1.0)
                tc = "white" if norm_v > 0.65 else "black"
                ax.text(j, i, _fmt(v), ha="center", va="center",
                        fontsize=5, color=tc, clip_on=True)
        ax.set_xticks(range(n_feat_cmp))
        ax.set_xticklabels(feat_cols_cmp, fontsize=6, rotation=45, ha="right")
        ax.set_xlabel("Feature", fontsize=8)
        ax.set_title(panel_title, fontsize=9)

    ax_l.set_yticks(range(n_ch_cmp))
    ax_l.set_yticklabels(ch_labels_cmp, fontsize=6)
    ax_l.set_ylabel("Channel", fontsize=8)

    # Separator line between real and pseudo-channels in both panels
    n_real_cmp = sum(1 for c in _all_channels if isinstance(c, int))
    if n_real_cmp < n_ch_cmp:
        for ax in (ax_l, ax_r):
            ax.axhline(n_real_cmp - 0.5, color="steelblue", linewidth=1.5, linestyle="--")

    fig.colorbar(im, ax=[ax_l, ax_r], label="|z-score|  (clamped at 50σ)",
                 shrink=0.5, pad=0.01)
    fig.suptitle(
        f"|z-score| comparison: raw vs config-normalised — {stem}\n"
        f"Grey cells in right panel = excluded by config (masked channels / disabled triggers).\n"
        f"Cells with lower |z| on the right = false positives suppressed by config integration.",
        fontsize=9, y=1.02,
    )
    fig.tight_layout()
    _save(fig, out_dir / f"{stem}_config_zscore_comparison.png", fmt)

    # ── 2g. Channel mask geometry ─────────────────────────────────────────────
    if ("triggerBoard.trigger_mask" in detector._trigger_config_vars
            and masked_channels):
        raw_df = pd.read_csv(filepath)
        geom   = (raw_df.groupby("channel")[["row", "column", "layer"]]
                        .first()
                        .reset_index())
        anom_dict = results["anomalous"].to_dict()

        layers = sorted(geom["layer"].unique())
        ncols  = len(layers)
        fig, axes = plt.subplots(1, ncols, figsize=(5 * ncols, 4), squeeze=False)

        for idx, layer in enumerate(layers):
            ax  = axes[0][idx]
            sub = geom[geom["layer"] == layer].copy()
            sub["row_plot"] = sub["row"].astype(float) + sub["channel"].apply(
                lambda c: 0.2 if c % 2 == 0 else -0.2
            )
            sub["is_masked"] = sub["channel"].isin(masked_channels)
            sub["is_anom"]   = sub["channel"].map(anom_dict).fillna(False)

            ok  = sub[~sub["is_masked"] & ~sub["is_anom"]]
            bad = sub[~sub["is_masked"] &  sub["is_anom"]]
            msk = sub[ sub["is_masked"]]

            if not ok.empty:
                ax.scatter(ok["column"],  ok["row_plot"],  c="steelblue",
                           s=120, zorder=3)
            if not bad.empty:
                ax.scatter(bad["column"], bad["row_plot"], c="tomato",
                           s=120, zorder=4)
            if not msk.empty:
                ax.scatter(msk["column"], msk["row_plot"], c="lightgrey",
                           s=200, marker="x", linewidths=2.5, zorder=3)

            ax.set_title(f"Layer {layer}")
            ax.set_xlabel("Column")
            ax.set_ylabel("Row")
            ax.set_xticks(sorted(sub["column"].unique()))
            ax.set_yticks(sorted(sub["row"].unique()))

        from matplotlib.lines import Line2D as _L2D
        legend_elems = [
            _L2D([0], [0], marker="o", color="w", markerfacecolor="steelblue",
                 markersize=10, label="Active — nominal"),
            _L2D([0], [0], marker="o", color="w", markerfacecolor="tomato",
                 markersize=10, label="Active — anomalous"),
            _L2D([0], [0], marker="x", color="dimgrey", markeredgewidth=2.5,
                 markersize=12, label="Masked by trigger_mask (not scored)"),
        ]
        fig.legend(handles=legend_elems, loc="lower center", ncol=3,
                   fontsize=8, framealpha=0.85, bbox_to_anchor=(0.5, 0.0))
        fig.suptitle(
            f"Channel trigger-mask state — {stem}\n"
            f"(grey × = silenced by triggerBoard.trigger_mask; excluded from reference and scoring)",
            y=1.01,
        )
        fig.tight_layout(rect=[0, 0.08, 1, 1])
        _save(fig, out_dir / f"{stem}_config_mask.png", fmt)


# ══════════════════════════════════════════════════════════════════════════════
# 3.  LOG SUMMARY PLOTS
# ══════════════════════════════════════════════════════════════════════════════

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
        'warn'  — sub-threshold persistent anomaly (n_persistent > 0 but below alert threshold)
        'pend'  — anomalous channels present but the run has fewer than
                  alert_consecutive_n files total, so persistence can never be verified
        'ok'    — no anomalous channels, or purely transient anomalies in a run that
                  has enough files for the streak to have been definitively broken
    """
    from collections import deque

    files_sorted = sorted(df["filename"].unique(), key=run_subrun_sort_key)

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

    # Pre-compute how many files each run contributes (used for short-run pend check).
    run_file_counts: dict = {}
    for fname in files_sorted:
        run_k, _ = run_subrun_sort_key(fname)
        run_file_counts[run_k] = run_file_counts.get(run_k, 0) + 1

    channel_history: dict = {}
    current_run:     object = None   # reset history at run boundaries
    rows = []

    for fname in files_sorted:
        run_k, sub_k = run_subrun_sort_key(fname)

        # Reset channel history when the run number changes, so that
        # the persistence window never spans two different runs.
        if run_k != current_run:
            current_run     = run_k
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

        # PEND only when the run has fewer files than the persistence window:
        # persistence can never be confirmed for any channel in such a run.
        # Transient anomalies in a long-enough run are OK (streak was broken).
        run_too_short = run_file_counts.get(run_k, 0) < alert_consecutive_n
        if n_persistent >= file_alert_n_channels or is_bulk or is_extreme:
            status = "alert"
        elif n_persistent > 0:
            status = "warn"
        elif n_transient > 0 and run_too_short:
            status = "pend"
        else:
            status = "ok"

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
    fmt: str = "png",
) -> None:
    """
    Up to six figures summarising the anomaly log.

    3a  log_anomaly_rate             — anomalous channel count per file, coloured by alert status
    3b  log_channel_frequency        — top-40 most frequently anomalous channels (skipped if none)
    3c  log_feature_frequency        — top-20 most triggered features (skipped if none)
    3d  log_run_summary              — per-run good-subrun fraction (raw status)
    3e  log_persistence_subrun_grid  — heatmap of persistence-aware status per run × subrun
    3f  log_persistence_run_summary  — bar chart of persistence-aware run quality
    """
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
    per_file["_sort_key"] = per_file["filename"].apply(run_subrun_sort_key)
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
                 "(red = ALERT · orange = WARN · light blue = PEND (persistence unverifiable) · blue = OK)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, out_dir / "log_anomaly_rate.png", fmt)

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
        _save(fig, out_dir / "log_channel_frequency.png", fmt)

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
        _save(fig, out_dir / "log_feature_frequency.png", fmt)

    # ── 3d. Per-run good-subrun fraction (raw, non-persistence-aware) ─────────
    per_file["_run"]    = per_file["filename"].apply(lambda f: run_subrun_sort_key(f)[0])
    per_file["_subrun"] = per_file["filename"].apply(lambda f: run_subrun_sort_key(f)[1])
    per_file["_status"] = per_file["filename"].map(file_status).fillna("ok")
    parseable = per_file[per_file["_run"] != float("inf")].copy()

    if parseable.empty:
        print("  No parseable run/subrun filenames — skipping run summary plot.")
    else:
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
        # pend = anomalous but persistence unverifiable → treat like warn (darkorange)
        bar_colors = [
            "steelblue"  if r.n_good == r.n_subruns else
            ("tomato"    if r.n_good == 0 and r.n_pend == 0 else
             "darkorange")
            for r in run_stats.itertuples()
        ]
        ax.bar(range(n_runs), run_stats["pct_good"],
               color=bar_colors, width=0.6, edgecolor="white", linewidth=0.5)

        # Annotate each bar with "ok/total (+pend PEND)"
        for i, row in enumerate(run_stats.itertuples()):
            label = (f"{int(row.n_good)}/{int(row.n_subruns)}"
                     if row.n_pend == 0 else
                     f"{int(row.n_good)}/{int(row.n_subruns)} (+{int(row.n_pend)}p)")
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
            + ")\nblue = all OK · orange = partial or anomalous · red = all ALERT"
            + "  (PEND = anomalous, persistence unverifiable)"
        )
        fig.tight_layout()
        _save(fig, out_dir / "log_run_summary.png", fmt)

    # ── 3e & 3f. Persistence-aware subrun grid and run summary ───────────────
    # status_df already computed at the top of this function
    _plot_persistence_subrun_grid(status_df, out_dir, alert_consecutive_n,
                                  file_alert_n_channels, single_file_alert_n_channels,
                                  single_file_alert_max_z, fmt=fmt)
    _plot_persistence_run_summary(status_df, out_dir, alert_consecutive_n,
                                  file_alert_n_channels, single_file_alert_n_channels,
                                  single_file_alert_max_z, fmt=fmt)

    print(f"  Log plots saved to {out_dir}/")


# ══════════════════════════════════════════════════════════════════════════════
# 4.  PERSISTENCE-AWARE PLOTS  (called from plot_log)
# ══════════════════════════════════════════════════════════════════════════════

# Status colour palette shared by both persistence plots.
# "pend" = anomalous channels in a run too short to verify persistence.
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
    fmt: str = "png",
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
        f"blue = OK · light blue = PEND (anomalous, short run) · orange = WARN"
        f" · red = ALERT · grey = no data",
        fontsize=9,
    )

    # Discrete colorbar legend
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor=_PERSIST_COLORS["ok"],      label="OK — no anomalies (or purely transient)"),
        Patch(facecolor=_PERSIST_COLORS["pend"],    label="PEND — anomalous, run too short to verify persistence"),
        Patch(facecolor=_PERSIST_COLORS["warn"],    label="WARN — sub-threshold persistent anomaly"),
        Patch(facecolor=_PERSIST_COLORS["alert"],   label="ALERT — persistent / bulk / extreme"),
        Patch(facecolor=_PERSIST_COLORS["no data"], label="no data"),
    ]
    ax.legend(handles=legend_elems, loc="upper right", fontsize=7,
              framealpha=0.85, bbox_to_anchor=(1.0, 1.0))

    fig.tight_layout()
    _save(fig, out_dir / "log_persistence_subrun_grid.png", fmt)


def _plot_persistence_run_summary(
    status_df: "pd.DataFrame",
    out_dir: Path,
    alert_consecutive_n: int,
    file_alert_n_channels: int,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
    fmt: str = "png",
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
    parseable["is_warn"] = parseable["status"] == "warn"
    parseable["is_pend"] = parseable["status"] == "pend"

    run_stats = (
        parseable.groupby("run")
                 .agg(n_subruns=("filename", "count"),
                      n_bad =("is_bad",  "sum"),
                      n_warn=("is_warn", "sum"),
                      n_pend=("is_pend", "sum"))
                 .assign(n_good=lambda x: x["n_subruns"] - x["n_bad"] - x["n_warn"] - x["n_pend"],
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
        if row.n_warn > 0:
            return _PERSIST_COLORS["warn"]
        if row.n_pend > 0:
            return _PERSIST_COLORS["pend"]
        return _PERSIST_COLORS["ok"]

    bar_colors = [_bar_color(row) for row in run_stats.itertuples()]

    ax.bar(range(n_runs), run_stats["pct_good"],
           color=bar_colors, width=0.6, edgecolor="white", linewidth=0.5)

    for i, row in enumerate(run_stats.itertuples()):
        label = f"{int(row.n_good)}/{int(row.n_subruns)}"
        if row.n_pend:
            label += f" +{int(row.n_pend)}p"
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
        f"blue = all OK · light blue = unverifiable (PEND) · orange = partial/WARN · red = all ALERT",
        fontsize=9,
    )
    fig.tight_layout()
    _save(fig, out_dir / "log_persistence_run_summary.png", fmt)


# ══════════════════════════════════════════════════════════════════════════════
# 5.  EVAL CONFUSION PLOT  (data written by evaluate.py, rendered here)
# ══════════════════════════════════════════════════════════════════════════════

_EVAL_PREDICT_COLORS = {   # bar fill colours keyed by predicted status
    "ok":    "steelblue",
    "warn":  "darkorange",
    "pend":  "lightsteelblue",
    "alert": "tomato",
}
_EVAL_STAT_ORDER = ["ok", "warn", "pend", "alert"]           # bar stack order (bottom → top)
_EVAL_GT_ORDER   = ["known_good", "not_certified", "unknown"] # x-axis bar order


def plot_eval_confusion(
    confusion_data_path: Path,
    plots_dir: Path,
    fmt: str = "png",
) -> None:
    """
    Render the evaluation confusion bar chart from eval_confusion_data.json.

    The JSON is written by evaluate.step_evaluate; this function is called by
    step_plots so the plot is produced alongside every other plot and respects
    --skip-all-plots / --plot-format.
    """
    import json as _json

    with open(confusion_data_path) as fh:
        data = _json.load(fh)

    gt_quality = data["gt_quality"]
    totals     = data["totals"]
    counts     = data["counts"]

    _plot_eval_confusion(counts, totals, gt_quality, plots_dir / "eval_confusion.png", fmt=fmt)


def _plot_eval_confusion(
    counts: dict,
    totals: dict,
    gt_quality: str,
    out_path: Path,
    fmt: str = "png",
) -> None:
    """Stacked bar chart of predicted status per ground-truth category."""
    active = [g for g in _EVAL_GT_ORDER if totals.get(g, 0) > 0]
    gt_display_active = {
        "known_good":    f"Known good\n({gt_quality})",
        "not_certified": "Not certified\ngood",
        "unknown":       "Unknown\n(not in catalogue)",
    }

    fig, ax = plt.subplots(figsize=(max(6, len(active) * 2.5), 5))
    bottom = [0] * len(active)

    for s in _EVAL_STAT_ORDER:
        vals = [counts[g].get(s, 0) for g in active]
        ax.bar(
            range(len(active)), vals,
            bottom=bottom,
            label=s.upper(),
            color=_EVAL_PREDICT_COLORS[s],
            width=0.55,
            edgecolor="white",
            linewidth=0.5,
        )
        for i, (v, b) in enumerate(zip(vals, bottom)):
            tot = totals[active[i]]
            if tot > 0:
                pct = v / tot * 100
                if pct >= 3:
                    ax.text(
                        i, b + v / 2,
                        f"{v}\n({pct:.0f}%)",
                        ha="center", va="center",
                        fontsize=8,
                        color="white" if s in ("ok", "alert") else "black",
                        fontweight="bold",
                    )
        bottom = [b + v for b, v in zip(bottom, vals)]

    for i, g in enumerate(active):
        ax.text(
            i, bottom[i] + max(bottom) * 0.01,
            f"N={totals[g]}",
            ha="center", va="bottom",
            fontsize=8, color="black",
        )

    ax.set_xticks(range(len(active)))
    ax.set_xticklabels([gt_display_active[g] for g in active], fontsize=10)
    ax.set_ylabel("Subruns (count)", fontsize=10)
    ax.set_title(
        f"Predicted status vs. ground-truth category\n"
        f"(ground truth: {gt_quality} quality from goodRunsListSlab.json)",
        fontsize=10,
    )
    ax.legend(loc="upper right", fontsize=9, title="Predicted", title_fontsize=9)
    fig.tight_layout()
    _save(fig, out_path, fmt)


# ══════════════════════════════════════════════════════════════════════════════
# 6.  PIPELINE STEP
# ══════════════════════════════════════════════════════════════════════════════

def step_plots(
    log_file: Path,
    models_dir: Path,
    plots_dir: Path,
    file_alert_n_channels: int,
    alert_consecutive_n: int,
    reports_dir: Path = None,
    single_file_alert_n_channels: int = 0,
    single_file_alert_max_z: float = 0.0,
    skip_subrun_plots: bool = False,
    max_subrun_plots: int = 10,
    fmt: str = "png",
) -> bool:
    """
    Generate all diagnostic plots for one pipeline run.

    Produces reference model plots, anomaly log summary plots, and (if
    reports_dir contains eval_confusion_data.json) the evaluation confusion
    chart.  Unless skip_subrun_plots is True, also generates per-file
    diagnostic plots for a sample of bad and good subruns.

    Parameters
    ----------
    log_file : Path
        Anomaly log CSV produced by the apply step.
    models_dir : Path
        Directory containing reference.npz and detector.pkl.
    plots_dir : Path
        Destination directory for all figures.
    file_alert_n_channels : int
        Persistent alert threshold used to colour bars and select bad subruns.
    alert_consecutive_n : int
        Persistence window used by the status replay logic.
    reports_dir : Path, optional
        If provided, checked for eval_confusion_data.json; when found the
        evaluation confusion chart is rendered into plots_dir.
    single_file_alert_n_channels : int
        Bulk single-file alert threshold forwarded to plot_log and plot_file.
    single_file_alert_max_z : float
        Extreme single-file alert threshold forwarded to plot_log and plot_file.
    skip_subrun_plots : bool
        When True, skip per-file diagnostic plots (reference + log still run).
    max_subrun_plots : int
        Per category cap on per-file plots: worst bad + N-1 random bad, N random
        good.  Pass -1 to plot every file (prints a loud warning).
    fmt : str
        Output format for all figures (png / pdf / svg).

    Returns
    -------
    bool
        True when plots were generated, False when auto-skipped because
        reference_means.<fmt> already exists in plots_dir.
    """
    print_step_header("STEP 5 — PLOTS")

    _sentinel = next(plots_dir.glob("reference_means.*"), None)
    if _sentinel is not None:
        print(f"[AUTO-SKIP] Plots — {_sentinel} already exists.")
        print(f"            Delete {plots_dir}/ to regenerate.")
        return False

    ref      = ReferenceModel.load(str(models_dir / "reference.npz"))
    detector = AnomalyDetector.load(str(models_dir / "detector.pkl"), ref)

    plots_dir.mkdir(parents=True, exist_ok=True)

    print("Reference plots...")
    plot_reference(ref, plots_dir, fmt=fmt)

    print("Log summary plots...")
    plot_log(str(log_file), plots_dir,
             file_alert_n_channels=file_alert_n_channels,
             alert_consecutive_n=alert_consecutive_n,
             single_file_alert_n_channels=single_file_alert_n_channels,
             single_file_alert_max_z=single_file_alert_max_z,
             fmt=fmt)

    if reports_dir is not None:
        confusion_data = reports_dir / "eval_confusion_data.json"
        if confusion_data.exists():
            print("Evaluation confusion plot...")
            plot_eval_confusion(confusion_data, plots_dir, fmt=fmt)

    if skip_subrun_plots:
        print("[SKIP] Per-file subrun plots (--skip-subrun-plots)")
        print(f"  Plots saved → {plots_dir}/")
        return

    print("Per-file plots (sample of good and bad subruns)...")
    df = pd.read_csv(str(log_file))
    per_file = (
        df.groupby("filename")
          .agg(total=("channel", "count"), n_bad=("anomalous", "sum"))
    )
    bad_df   = per_file[per_file["n_bad"] >= file_alert_n_channels].sort_values("n_bad", ascending=False)
    good_df  = per_file[per_file["n_bad"] <  file_alert_n_channels]

    bad_names  = bad_df.index.tolist()
    good_names = good_df.index.tolist()

    n_bad  = len(bad_names)
    n_good = len(good_names)

    if max_subrun_plots == -1:
        print()
        print("!" * 60)
        print("  WARNING: max_subrun_plots = -1")
        print(f"  This will generate plots for ALL {n_bad} bad and ALL {n_good} good file(s).")
        print("  For large runs this can be very slow and use significant")
        print("  disk space.  Set  \"max_subrun_plots\": N  in config.yaml")
        print("  (or pass --max-subrun-plots N) to cap the output.")
        print("!" * 60)
        print()
        plot_bad  = bad_names
        plot_good = good_names
    else:
        if bad_names:
            worst     = bad_names[:1]
            remaining = bad_names[1:]
            n_extra   = min(max_subrun_plots - 1, len(remaining))
            plot_bad  = worst + random.sample(remaining, n_extra)
        else:
            plot_bad = []

        plot_good = random.sample(good_names, min(max_subrun_plots, len(good_names)))

        print(f"  Plotting {len(plot_bad)}/{n_bad} bad file(s) "
              f"(worst + {len(plot_bad)-1 if plot_bad else 0} random) "
              f"and {len(plot_good)}/{n_good} good file(s) (random).")

    plot_names = plot_bad + plot_good

    path_cache_file = log_file.parent / (log_file.stem + "_paths.txt")
    if path_cache_file.exists():
        path_map = {Path(p).name: p for p in path_cache_file.read_text().splitlines() if p.strip()}
    else:
        path_map = {}

    n_plotted = 0
    for name in plot_names:
        full_path = path_map.get(name)
        if full_path is None:
            print(f"    [SKIP] {name} — full path not in cache, re-run with --apply-list to rebuild")
            continue
        out = plots_dir / Path(full_path).stem
        out.mkdir(parents=True, exist_ok=True)
        print(f"  {name}")
        try:
            plot_file(full_path, detector, out,
                      single_file_alert_n_channels=single_file_alert_n_channels,
                      single_file_alert_max_z=single_file_alert_max_z,
                      fmt=fmt)
            n_plotted += 1
        except Exception as exc:
            print(f"    [ERROR] {exc}", file=sys.stderr)

    print(f"\n  {n_plotted}/{len(plot_names)} file(s) plotted ({len(plot_bad)} bad, {len(plot_good)} good).")
    print(f"  All plots saved → {plots_dir}/")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _save(fig: plt.Figure, path: Path, fmt: str = "png") -> None:
    """Save fig to path with the suffix replaced by fmt, then close it."""
    path = Path(path).with_suffix(f".{fmt}")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"    {path.name}")


def _load_models(models_dir: str) -> AnomalyDetector:
    """Load and return the AnomalyDetector from models_dir; exit with an error if missing."""
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
    add_plot_format(parser, cfg)

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
        plot_reference(detector.reference, out_dir, fmt=args.plot_format)

    elif args.command == "file":
        detector = _load_models(args.models_dir)
        plot_file(args.csv, detector, out_dir,
                  single_file_alert_n_channels=args.single_file_alert_n_channels,
                  single_file_alert_max_z=args.single_file_alert_max_z,
                  fmt=args.plot_format)

    elif args.command == "log":
        if not Path(args.log_file).exists():
            print(f"ERROR: Log file not found: {args.log_file}", file=sys.stderr)
            sys.exit(1)
        plot_log(args.log_file, out_dir,
                 file_alert_n_channels=args.file_alert_n_channels,
                 alert_consecutive_n=args.alert_consecutive_n,
                 single_file_alert_n_channels=args.single_file_alert_n_channels,
                 single_file_alert_max_z=args.single_file_alert_max_z,
                 fmt=args.plot_format)


if __name__ == "__main__":
    main()
