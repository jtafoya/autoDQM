"""Presentation figures from previously computed matrices and saved response text."""
from pathlib import Path
import json
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
INK = "#183247"
ACCENT = "#ac3d17"
STABILITY = {
    1620: "DAQ transient/restart direction recurs; the concrete cause remains unknown.",
    1640: "Trials 1/3 emphasize channel-pair readout faults; trial 2 retains suppression/readout alternatives; trials 4/5 emphasize mask/config mismatch.",
    1642: "All five categories describe localized LVDS signal loss; the physical root cause remains qualified.",
    1702: "Broad digitizer/processing/configuration/reference hypotheses recur, without one resolved mechanism.",
    1703: "A global waveform-feature/configuration/reference interpretation recurs; the mechanism remains unresolved.",
    2126: "All five categories favor digitizer/DAQ readout loss, with the concrete cause left uncertain.",
}


def read(path):
    return json.loads(Path(path).read_text())


def wrap(text, width):
    return "\n".join(textwrap.wrap(str(text), width=width, break_long_words=True, break_on_hyphens=False))


def matrix(run, suffix):
    return pd.read_csv(HERE / f"run{run}" / f"run{run}_matrix_{suffix}.csv", index_col=0)


def observed_notes(run, maximum, frequency, counts, meta):
    coverage = pd.read_csv(HERE / f"run{run}/channel_coverage.csv")
    values = frequency.to_numpy()
    valid = np.isfinite(values)
    persistent = int((valid & (values >= 0.8)).sum())
    notes = [f"{meta['matrix_valid_subruns']}/{meta['total_subruns']} subruns have defined z values; "
             f"{len(meta['missing_or_no_data_subruns'])} missing/empty/no-z.",
             f"{persistent} cells exceed |z|>{meta['z_threshold']:g} in at least 80% of their valid subruns."]
    ranked = sorted(zip(*np.where(valid & (values > 0))),
                    key=lambda ij: (values[ij], maximum.to_numpy()[ij]), reverse=True)[:4]
    notes.append("Most persistent cells (not a cause ranking):")
    for i, j in ranked:
        notes.append(f"  ch{frequency.index[i]} / {frequency.columns[j]}: "
                     f"{values[i,j]:.1%}; max {maximum.iloc[i,j]:.3g}; n={int(counts.iloc[i,j])}.")
    absent = coverage[coverage.subruns_absent > 0].sort_values("subruns_absent", ascending=False)
    if len(absent):
        notes.append("Channel absence is separate from z:")
        for row in absent.head(4).itertuples():
            notes.append(f"  ch{row.channel}: absent in {row.subruns_absent}/{row.detector_valid_subruns} detector subruns.")
    if run == 1640:
        notes.append("Frozen IF model has trigger-config masking OFF. Mask text mentions do not establish masked digitizer channels.")
    if run == 2126:
        notes.append("Coverage limitation: Phase 1 Trigger/LVDS text covers only subruns 1-40; IF report covers 86 subruns.")
    return notes


def mention_notes(mentions):
    notes = ["Counts are trials, not word occurrences.",
             "Text counts include hypotheses/checks; observed-section mentions are shown separately."]
    candidates = mentions[(mentions.kind == "context") & (mentions.llm_mention_count > 0)].copy()
    candidates = candidates.sort_values("llm_mention_count", ascending=False, kind="stable")
    for row in candidates.head(9).itertuples():
        label = row.item.replace(" (hypothesis or check)", "")
        notes.append(f"{label}: {row.llm_mention_count}/5 text; {row.observed_mention_count}/5 observed-section.")
    cells = mentions[(mentions.kind == "cell") & (mentions.llm_mention_count > 0)]
    notes.append(f"Unambiguous target-observation cell links: {len(cells)}.")
    notes.append("No channel-feature Cartesian expansion. Generic pulse statistics, LVDS pins, mask state and missing-channel text remain notes.")
    return notes


def render_run(run, global_max):
    directory = HERE / f"run{run}"
    maximum = matrix(run, "max_abs_z")
    frequency = matrix(run, "anomaly_frequency")
    counts = matrix(run, "valid_subrun_count")
    meta = read(directory / "metadata.json")
    predictions = read(directory / "phase1_predictions.json")
    mentions = pd.read_csv(directory / f"run{run}_llm_mentions.csv", keep_default_na=False)
    channels = [str(x) for x in maximum.index]
    features = list(maximum.columns)
    ch_counts = {str(row.item): int(row.llm_mention_count) for row in mentions[mentions.kind == "channel"].itertuples()}
    f_counts = {row.item: int(row.llm_mention_count) for row in mentions[mentions.kind == "feature"].itertuples()}
    cell_mentions = mentions[(mentions.kind == "cell") & (mentions.llm_mention_count > 0)]
    plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42, "ps.fonttype": 42})
    fig = plt.figure(figsize=(24, 20), facecolor="white")
    fig.text(.04, .978, f"Run {run} | Observed Signature and LLM-Mentioned Evidence", fontsize=24, color=INK, weight="bold")
    fig.text(.04, .955, f"Frozen IF reference | {len(channels)} channels x {len(features)} features | "
             f"{meta['matrix_valid_subruns']}/{meta['total_subruns']} valid detector subruns | "
             f"strict threshold |z| > {meta['z_threshold']:g} | 5 saved Sol trials", fontsize=12, color=INK)
    fig.text(.04, .937, "Matrix: digitizer-only model; original feature order and settings. "
             "Orange label [n] = explicit text mention in n/5 trials, not internal model attribution.", fontsize=10.5, color=ACCENT)
    positions = [.047, .542]
    axes = []
    for x, frame, title, is_frequency in zip(positions, [maximum, frequency], ["MAX |z|", "ANOMALY FREQUENCY"], [False, True]):
        ax = fig.add_axes([x, .415, .412, .485])
        axes.append(ax)
        cmap = plt.get_cmap("YlGnBu" if is_frequency else "magma_r").copy()
        cmap.set_bad("#d7dbdf")
        if is_frequency:
            im = ax.imshow(frame.to_numpy(), aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=1)
        else:
            norm = SymLogNorm(linthresh=meta["z_threshold"], linscale=1.0, vmin=0, vmax=global_max, base=10)
            im = ax.imshow(frame.to_numpy(), aspect="auto", interpolation="nearest", cmap=cmap, norm=norm)
        ax.set_yticks(range(len(channels)))
        ax.set_yticklabels([f"ch{ch}" + (f" [{ch_counts[ch]}]" if ch_counts.get(ch, 0) else "") for ch in channels], fontsize=6.5)
        ax.set_xticks(range(len(features)))
        ax.set_xticklabels([f + (f" [{f_counts[f]}]" if f_counts.get(f, 0) else "") for f in features], rotation=60, ha="right", fontsize=8.3)
        for label, ch in zip(ax.get_yticklabels(), channels):
            if ch_counts.get(ch, 0):
                label.set_color(ACCENT)
                label.set_fontweight("bold")
        for label, feature in zip(ax.get_xticklabels(), features):
            if f_counts.get(feature, 0):
                label.set_color(ACCENT)
                label.set_fontweight("bold")
        ax.tick_params(axis="both", length=0, pad=3)
        for boundary in range(16, len(channels), 16):
            ax.axhline(boundary - .5, color="white", lw=.65, alpha=.9)
        for row in cell_mentions.itertuples():
            ch = str(int(float(row.channel)))
            if ch in channels and row.feature in features:
                i, j = channels.index(ch), features.index(row.feature)
                ax.add_patch(Rectangle((j-.48, i-.48), .96, .96, fill=False, edgecolor="white", linewidth=2.3))
                ax.add_patch(Rectangle((j-.48, i-.48), .96, .96, fill=False, edgecolor=ACCENT, linewidth=1.1))
        ax.set_title(title, loc="left", fontsize=16, weight="bold", color=INK, pad=28)
        color_ax = fig.add_axes([x + .23, .910, .182, .009])
        cb = fig.colorbar(im, cax=color_ax, orientation="horizontal")
        if is_frequency:
            cb.set_ticks([0, .25, .5, .75, 1])
            cb.set_ticklabels(["0%", "25%", "50%", "75%", "100%"])
        else:
            ticks = [0, meta["z_threshold"], 100, 10000, 1000000]
            ticks = [v for v in ticks if v <= global_max]
            cb.set_ticks(ticks)
            cb.set_ticklabels([f"{v:g}" for v in ticks])
        cb.ax.tick_params(labelsize=8, length=2, pad=2)
    fig.text(.047, .315, "Max values are NOT clipped; nonlinear color scale resolves both small and million-scale z. "
             "Frequency uses each cell's own valid-subrun denominator.", fontsize=10, color=INK)
    fig.text(.047, .299, "Grey = undefined / masked / no data, not zero. Missing channels are excluded from cell denominators "
             "and separately counted below. Orange cell borders require an explicit channel-feature link.", fontsize=10, color=INK)
    obs = observed_notes(run, maximum, frequency, counts, meta)
    mnotes = mention_notes(mentions)
    diagnosis = []
    for i, p in enumerate(predictions, 1):
        diagnosis.append(f"Trial {i}: {p['category']}")
    diagnosis.append("Reading across trials: " + STABILITY[run])
    diagnosis.append("Category text is reproduced from saved responses; it is not a true-cause label.")
    for x, title, notes in zip([.047, .37, .69], ["OBSERVED MATRIX", "LLM-MENTIONED EVIDENCE", "PHASE 1 DIAGNOSES (saved category)"], [obs, mnotes, diagnosis]):
        fig.text(x, .272, title, fontsize=13, weight="bold", color=INK)
        separator = "\n" if title == "LLM-MENTIONED EVIDENCE" else "\n\n"
        text = separator.join(wrap(n, 69) for n in notes)
        fig.text(x, .255, text, fontsize=10, color=INK, va="top", linespacing=1.3)
    fig.text(.047, .026, "Source: study_20260906T044011Z_7ac63c5a | "
             "Reference: juan_reproduction_digi_z8_if0001_train20_seed42_noTrigger_noLVDS_ignoreTriggerConfig", fontsize=9, color="#566775")
    fig.text(.047, .012, "Offline visualization only. No new LLM calls. No ground-truth selection. "
             "Explicit mentions are not evidence of internal causal use by the LLM.", fontsize=9, color="#566775")
    fig.savefig(directory / f"run{run}_feature_matrix.png", dpi=200, facecolor="white")
    fig.savefig(directory / f"run{run}_feature_matrix.pdf", facecolor="white")
    plt.close(fig)
    return obs, mnotes, meta


def render_all(runs):
    all_available = [r for r in (1620, 1640, 1642, 1702, 1703, 2126) if (HERE / f"run{r}/run{r}_matrix_max_abs_z.csv").exists()]
    global_max = max(float(np.nanmax(matrix(r, "max_abs_z").to_numpy())) for r in all_available)
    global_max = float(10 ** np.ceil(np.log10(max(global_max, 10))))
    rows = []
    for run in runs:
        obs, mentions, meta = render_run(run, global_max)
        counts = pd.read_csv(HERE / f"run{run}/run{run}_llm_mentions.csv")
        chosen = counts[(counts.kind == "context") & (counts.llm_mention_count >= 3)]
        mentioned = "; ".join(f"{r.item}: {r.llm_mention_count}/5" for r in chosen.itertuples())
        rows.append(f"| {run} | {' '.join(obs[:6])} | {mentioned} | {STABILITY[run]} |")
        print(f"Rendered run{run}: PNG + PDF", flush=True)
    lines = ["# Phase 1: observed matrices and LLM-mentioned evidence", "",
             "Offline visualization from the frozen campaign model and existing five responses per run. "
             "Mentions are deterministic text matches, not internal model attribution. No new API calls or ground truth are used.", "",
             "| Run | Main observed signature | Repeated LLM-mentioned evidence | Cause stability |",
             "|---|---|---|---|", *rows, "",
             "## Matrix definition and coverage", "",
             "The original model contains 96 digitizer channels and 29 ordered features. Trigger/LVDS and trigger-config "
             "normalization/masking are disabled in this campaign. No pseudochannels are added. The z threshold is read "
             "from detector.pkl and checked against frozen training metadata (8 here; strict >). The reference's original "
             "standard-deviation floor of 1e-6 is retained, so very large z values remain possible.", "",
             "Max |z| is computed without clipping. Anomaly frequency divides cell exceedances by that cell's finite-z "
             "subruns, not by all run files. Undefined cells are blank in numeric CSVs and grey in figures. Per-cell "
             "denominators, exceedance counts, channel-presence coverage and all per-subrun z arrays are exported.", "",
             "Run2126 saved Trigger/LVDS context covers subruns 1-40, whereas its IF report covers 86 subruns. The matrices "
             "use all available detector subruns. Coverage limitations must not be interpreted as proof of globally normal telemetry.", "",
             "## Reading the text markers", "",
             "Orange channel/feature labels show per-trial explicit mentions, excluding sentences containing explicit historical-run "
             "references. These text counts may include inferred hypotheses and proposed checks; the quote CSV preserves field, "
             "scope, trial and verbatim text. Observed-only counts are separate. Cell borders require direct exact feature/channel "
             "syntax in target OBSERVED text. Mere sentence co-occurrence, generic pulse statistics, pin-to-channel inference "
             "and feature-only/channel-only references never produce a cell overlay. A zero cell-link count means no "
             "unambiguous link was extracted, not that the model ignored the feature.", "",
             "Observed-section counts are lexical mentions within the saved OBSERVED section, not a positivity or correctness "
             "judgment: negated statements and unavailable telemetry are retained as quoted. Category underscores are treated "
             "as word separators for context phrases only. Recognized cell bindings include direct adjacency, feature-on-channel, "
             "and single-channel has/shows/exhibits/across constructions with an exact feature name and no intervening channel.", "",
             "Missing-channel behavior is a separate detector state, not a z-matrix feature. Cause stability text summarizes "
             "the existing saved categories; no new physics taxonomy or automatic semantic classifier is introduced.", "",
             "## Files and regeneration", "",
             "Each run directory contains the requested PNG/PDF, maximum/frequency/mention CSVs, plus valid-subrun and "
             "exceedance matrices, subrun/channel coverage, signed-z NPZ, quoted mentions, copied saved predictions and metadata.", "",
             "```bash", "cd /afs/cern.ch/user/p/pengy/autoDQM/isolation_forest",
             "PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/novel/randomness/feature_matrix/build_feature_matrices.py --workers 2",
             "```", "", "For layout-only regeneration from saved matrices, append `--stage render`.", ""]
    (HERE / "feature_matrix_summary.md").write_text("\n".join(lines))
