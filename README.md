# AutoDQM

This repository contains the basis for developing an Automated Anomaly Detection system system (AutoDQM, see https://arxiv.org/pdf/2501.13789 for reference) initially designed for MilliQan slab data. Different techniques are explored.


## Isolation Forest

A two-layer anomaly detector for MilliQan slab Digitizer data, implemented in
`isolation_forest/`.  Each Digitizer CSV is compressed to one feature vector per channel
(mean, std, median of 11 metrics + occupancy + dead fraction), and optionally augmented
with TriggerBoard rates and LVDS pin counts.

**Layer 1 — Statistical z-score**: compares each per-channel feature against a reference
built from known-good runs using Welford's online algorithm.  Channels deviating more than
`z_threshold` σ from the reference mean are flagged.  Catches individual feature drift,
dead channels, gain shifts, and timing anomalies.

**Layer 2 — Isolation Forest**: trained on z-scored good-data vectors.  The algorithm
randomly partitions the feature space; points that are isolated in fewer splits receive a
lower (more negative) anomaly score and are flagged as anomalous.  Because it operates on
the full multivariate feature vector, it catches correlated anomalies and novel failure
modes that do not show up as a large z-score in any single feature.

A channel is flagged if either layer triggers.  Alerts are suppressed for single-file
fluctuations via a configurable persistence window: a channel must be anomalous in
`alert_consecutive_n` consecutive subruns before an `[ALERT]` is raised.

See [`isolation_forest/README.md`](isolation_forest/README.md) for the full workflow,
configuration reference, and performance-tuning guide.
