"""
autoDQM isolation-forest package.

Modules
-------
features    — per-channel feature extraction from Digitizer CSV files
reference   — Welford online reference model
detector    — two-layer anomaly detector (z-score + Isolation Forest)
run_list    — Digitizer filename utilities and run-list parsers
run_config  — MilliDAQ trigger/DAQ config parsing
monitor     — batch and live-watch apply logic
train       — step_train: reference build + IF training
evaluate    — step_evaluate: ground-truth cross-reference and confusion output
report      — step_report: per-run quality classification
combine     — step_combine_specific_runs: per-run log aggregation
plot        — step_plots: all visualisations
pipeline    — full train → apply → evaluate → report → plots orchestrator
config      — config-file loading and step-header formatting
args        — shared argparse helpers and flag resolvers
"""
