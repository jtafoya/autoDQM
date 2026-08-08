# TASK 1 range-aware knowledge-base scan

This workflow separates expensive detector application from cheap,
repeatable post-processing.

1. `campaign.py prepare` validates and deserializes the frozen model, verifies
   its metadata and feature flags, snapshots provenance, and generates the
   1500-3000 run manifest plus an HTCondor submit file.
2. Each Condor process calls `run_kb_scan_job.sh` for one run. The job uses the
   existing `src.pipeline --apply-specific-run` path, publishes validated output
   atomically, and records `completed`, `no_data`, or `failed` in `status.json`.
   Completed/no-data jobs are safe to resubmit and skip automatically.
3. `src.kb_scan` replays the canonical alert logic, applies the >=10 valid
   subruns and >=3 consecutive ALERT rule, creates deterministic signatures,
   audits neighboring-run similarity, absorbs only observed interior short-run
   bridges, and writes a range-aware KB candidate. It never replaces the
   production KB.

Post-processing refuses to generate a candidate while any run is `failed` or
`incomplete`. `--allow-incomplete` exists only for explicit smoke-test audits.

The generated campaign directory contains run-specific anomaly logs, input
manifests, job state, Condor stdout/stderr/logs, provenance, and all required
post-processing products. Similarity thresholds and component weights are in
`configs/kb_scan_task1.yaml`, so clustering can be rerun without rescoring data.

From `/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest`:

```bash
# Validate the frozen model and (re)generate the manifest/submit description.
python3 condor/kb_scan/campaign.py prepare --config configs/kb_scan_task1.yaml

# The operator launches this command only after reviewing the generated files.
condor_submit kb_scan_campaigns/kb_task1_runs1500_3000_juan_v1/condor/submit.sub

# This exits nonzero until every run is completed or explicitly no_data.
python3 condor/kb_scan/campaign.py status \
  --config configs/kb_scan_task1.yaml --require-complete

# Cheap, repeatable aggregation/range clustering/KB-candidate generation.
python3 -m src.kb_scan --config configs/kb_scan_task1.yaml
```

Do not submit the full campaign during implementation or smoke testing. The
operator must run the generated `condor/submit.sub` manually.
