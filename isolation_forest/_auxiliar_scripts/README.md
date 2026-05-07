# Auxiliary scripts — 260429 sweep analysis

One-off analysis and plotting scripts for the 260429 parameter sweep
(contamination × z-threshold × quality × feature variant).

## Plotting scripts

### `compare_sweep_260429_onTrainingSample.py`
Plots FP/TN for each model evaluated against its **own training quality** as ground truth.
Each page of the output PDF covers one quality tier (Loose / Medium / Tight); lines are
differentiated by feature variant (colour) and triggerConfig setting (solid/dashed).
Produces four PDFs in `plots/`:
- `fp_sweep_260429_onTrainingSample_counts.pdf` / `tn_sweep_260429_onTrainingSample_counts.pdf` — absolute counts
- `fp_sweep_260429_onTrainingSample_rel.pdf` / `tn_sweep_260429_onTrainingSample_rel.pdf` — rates (%)

### `compare_sweep_260429_onSameRefSample.py`
Plots FP/TN rate for all models evaluated against all three goodRunsList qualities in a single
run, so Loose/Medium/Tight-trained models can be compared on equal footing. All three training
qualities appear as separate line styles on the same axes; pages separate triggerConfig variants.
Y-axis range is controlled by the `FIX_Y_RANGE` flag at the top of the file (fixed or automatic).
Produces six PDFs in `plots/` (two per catalogue quality):
- `fp_sweep_260429_on{Loose,Medium,Tight}_rel.pdf` / `tn_sweep_260429_on{Loose,Medium,Tight}_rel.pdf`

### `compare_applyToRuns_260429_onSameRefSample.py`
Plots four metrics for models applied to the full run-by-run dataset (applyToRuns),
covering contamination ∈ {0.005, 0.01} × z = 7σ. Runs over all three catalogue qualities in a
single go; all three training qualities shown as separate line styles on the same axes.
Columns per page: FP | TN (known-good subruns/runs) | NL-GOOD | NL-ALERT (subruns/runs absent
from the goodRunsList entirely). Relative plots fix the y-axis to 0–100 %.
Produces six PDFs in `plots/` (one per quality × one per counts/rel):
- `applyToRuns_260429_on{Loose,Medium,Tight}_counts.pdf`
- `applyToRuns_260429_on{Loose,Medium,Tight}_rel.pdf`

## Utility scripts

### `combine_and_evaluate_applyToRuns_260429.sh`
Combines and evaluates applyToRuns outputs for the 260429 sweep.

### `fill_missing_EXT_reports.sh`
Fills in missing report directories for the EXT extension jobs.
