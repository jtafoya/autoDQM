# Per-run Isolation Forest scan utility

This directory retains only the reusable, provenance-checked machinery for
applying an already-trained Isolation Forest to one run at a time. The former
Task-1 run-level interpretation, candidate generation, range aggregation, and
recovery/retry workflow have been retired.

`campaign.py` can validate a frozen model, prepare a new scan campaign from a
new configuration, and run one detector job. `run_kb_scan_job.sh` is the
matching worker entrypoint. No active Task-1 configuration is kept here; a new
workflow must use a new campaign tag and configuration.

The completed legacy campaign remains under `kb_scan_campaigns/` only as an
archive of low-level per-subrun results and their provenance. Do not use it to
derive the retired run-level classifications.
