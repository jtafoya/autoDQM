# Auxiliary scripts — 260429 sweep analysis

One-off analysis and plotting scripts for the 260429 parameter sweep and its extensions.

---

## Original 260429 sweep

### `compare_sweep_260429_onTrainingSample.py`
FP/TN for each model evaluated against its **own training quality** as ground truth.
Pages: quality tier; lines: feature variant (colour) × triggerConfig (solid/dashed); x: contamination.
Produces four PDFs in `plots/`:
- `fp_sweep_260429_onTrainingSample_{counts,rel}.pdf`
- `tn_sweep_260429_onTrainingSample_{counts,rel}.pdf`

### `compare_sweep_260429_onSameRefSample.py`
FP/TN rate for all models against each catalogue quality so training qualities can be compared.
Pages: triggerConfig; lines: feature variant (colour) × training quality (style); x: contamination.
`FIX_Y_RANGE` flag at the top controls y-axis limits.
Produces six PDFs in `plots/` (two per catalogue quality):
- `fp_sweep_260429_on{Loose,Medium,Tight}_rel.pdf`
- `tn_sweep_260429_on{Loose,Medium,Tight}_rel.pdf`

### `compare_applyToRuns_260429_onSameRefSample.py`
FP/TN/NL-GOOD/NL-ALERT for models applied run-by-run, covering cont ∈ {0.005, 0.01} × z = 7σ.
Reads from `reports/applyToRuns_260429/`.
Produces six PDFs in `plots/`:
- `applyToRuns_260429_on{Loose,Medium,Tight}_{counts,rel}.pdf`

### `combine_and_evaluate_applyToRuns_260429.sh`
Combines per-run CSVs and evaluates (reports + plots) for the 260429 apply-to-runs exercise.

---

## 260429 EXT extension (low-contamination / high-z best region)

### `compare_applyToRuns_260429_EXT_onSameRefSample.py`
FP/TN/NL-GOOD/NL-ALERT for 12 EXT models applied run-by-run
(cont ∈ {0.001, 0.002} × z ∈ {7, 8}σ, trigger+LVDS, ignoreDAQConfig).
Pages: one per catalogue quality; lines: z-threshold (colour) × training quality (style); x: contamination.
Reads from `reports/applyToRuns_260429_EXT/`.
Produces six PDFs in `plots/`:
- `applyToRuns_260429_EXT_on{Loose,Medium,Tight}_{counts,rel}.pdf`

### `combine_and_evaluate_applyToRuns_260429_EXT.sh`
Combines per-run CSVs (`logs/applyToRuns_260429_EXT/`) and evaluates (reports only, no plots)
for the 12 EXT apply-to-runs models. Run before the compare script above.

### `fill_missing_EXT_reports.sh`
Fills in missing report directories for the full EXT training-sample evaluation.

---

## 260429 IFhp hyperparameter sweep (n_estimators × max_samples at the best EXT point)

All three scripts share the same axes convention:
- **x-axis**: `if_n_estimators` (200, 300, 500)
- **columns**: `if_max_samples` (256, 1024, 4096)
- **colour**: contamination (0.001 blue, 0.002 orange) or training quality
- **line style**: z_threshold (7σ solid, 8σ dashed) or training quality

### `compare_sweep_260429_IFhp_onTrainingSample.py`
FP/TN for each model evaluated against its **own training quality**.
Pages: quality; cols: max_samples; lines: contamination (colour) × z (style); x: n_estimators.
Reads from `reports/<tag>/`.
Produces four PDFs in `plots/`:
- `fp_sweep_260429_IFhp_onTrainingSample_{counts,rel}.pdf`
- `tn_sweep_260429_IFhp_onTrainingSample_{counts,rel}.pdf`

### `compare_sweep_260429_IFhp_onSameRefSample.py`
FP/TN rate for all IFhp models against each catalogue quality so training qualities can be compared.
Pages: cont × z combo (4 pages); cols: max_samples; lines: training quality (colour + style); x: n_estimators.
Reads from `reports/<tag>/`.
Produces six PDFs in `plots/`:
- `fp_sweep_260429_IFhp_on{Loose,Medium,Tight}_rel.pdf`
- `tn_sweep_260429_IFhp_on{Loose,Medium,Tight}_rel.pdf`

### `combine_and_evaluate_applyToRuns_260429_IFhp.sh`
Combines per-run CSVs (`logs/applyToRuns_260429_IFhp/`) and evaluates (reports only, no plots)
for all 108 IFhp apply-to-runs models. Skips models with no per-run CSVs.
Run before the compare script below.

### `compare_applyToRuns_260429_IFhp_onSameRefSample.py`
FP/TN/NL-GOOD/NL-ALERT for all 108 IFhp models applied run-by-run.
Pages: cont × z combo (4 pages); cols: FP | TN | NL-GOOD | NL-ALERT;
lines: training quality (colour + style); marker size: max_samples; x: n_estimators.
Reads from `reports/applyToRuns_260429_IFhp/`.
Produces six PDFs in `plots/`:
- `applyToRuns_260429_IFhp_on{Loose,Medium,Tight}_{counts,rel}.pdf`

---

## Training-fraction scan (batch_submit.sh DAG)

### `compare_scan_trainFrac.py`
Collapses the per-fraction reports of the training-fraction scan into one summary figure.
Panels: known-good | not-certified subruns; lines: verdict rate (ok/warn/pend/alert, colour);
x: training fraction. Ground truth: good_run_list_TRAINING.txt (from `eval_confusion_data.json`).
Reads from `reports/scan_trainFracSweep/` (override with `--reports-dir`).
Produces one PDF in `plots/`:
- `scan_trainFrac_summary_rel.pdf`

Also prints a per-fraction table of raw counts. Run after the scan's combine phase has
finished for every fraction (partially-finished fractions are skipped with a warning).

---

## False-positive mechanism analysis (pengy repro, 2026-07-27 baseline)

### `sigma_census.py`
Maps every low-variance (channel, feature) cell in a trained `reference.npz` —
the "Mechanism A" landmines behind sigma-explosion extreme alerts (the std floor
in `src/reference.py` is a 1e-6 division guard, not a statistical floor, so a
feature constant in training gives z ~ 1e6 on any deviation).
Reports cells that are constant (sigma < 1e-6), extreme landmines
(sigma <= 1/z_extreme: a unit jump fires the extreme alert), and flag landmines
(sigma <= 1/z_threshold). `--out-csv` writes the full cell table.
On the repro_pengy reference: 335/2784 cells are extreme landmines
(frac_dead 96/96 channels, occupancy 95, sideband_rms_median 83,
nPulses_median 50, nPulses_mean 11).

### `fp_mechanism_scan.py`
Decomposes a known-good apply log's alerts by mechanism and rescans the
decision-layer parameters OFFLINE — no re-apply, because the log stores
per-channel `max_z` + `if_score` and subrun status is replayed from them
(imports `src.plot._compute_persistence_status`; no duplicated logic).
Sections: (1) baseline + exclusive persistent/bulk/extreme decomposition and
worst runs; (2) landmine variants — V1 defuses the extreme rule on landmine-only
rows, V2 additionally unflags z-only landmine rows (approximates a
variance-floor retrain); (3) grids over the single-file and persistence
parameters; (4) optional `--z-rescan` raising z_threshold offline (lowering it
needs a re-apply — sub-threshold z values are not logged).
Run from `isolation_forest/` against the combined log and the model's
`reference.npz`.

### `llm_model_eval.py`
Compares LLM models on the alert-categorization task using elog-labelled KB
runs as ground truth. Builds test alerts by replaying the canonical alert
logic on supplied anomaly logs, then queries each model with the production
prompt from `src/llm.py` — with the tested run's own KB entry REMOVED
(leave-one-out), so success requires signature matching, not run-number
lookup. Case types: `matchable` (category has a sibling entry — core accuracy),
`unmatchable` (singleton category — scores honesty: a confident wrong assertion
fails), `control` (no hold-out — sanity, expect ~100%). `--dry-run` prints the
case table and prompt size without any API calls; defaults bound cost
(3 models max, 2 alerts/run, 15-case cap).
