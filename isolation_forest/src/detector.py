"""
Two-layer anomaly detector:

  Layer 1 — Statistical (z-score):
      Compares each per-channel feature against the reference mean ± N·std.
      Catches individual feature drift and known failure modes (noisy/dead channels).

  Layer 2 — Isolation Forest trained on z-scored good data:
      Detects multivariate anomalies and novel failure modes that don't show up
      as a single large z-score but break the correlation structure of nominal data.
      Trained only on good data → inherently a novelty detector.

Both layers run per channel. A channel is flagged if either layer triggers.

Absent data sources (LVDS)
--------------------------
Not every run has an LVDS file.  When LVDS is absent:

  - Real channels (ch0, ch1, ...): the LVDSpin feature is NaN.  NaN z-scores
    are transparent to Layer 1 (NaN > threshold = False) and are filled with 0.0
    (= perfectly nominal) before Layer 2 scoring.  No anomaly is raised.

  - trigger_lvds_total pseudo-channel: all features are NaN.  The channel IS
    known to the reference (seen during training), so it is treated as nominal —
    all-NaN z-scores do not trigger either layer.  It is never marked as
    "new_channel" or "missing_channel".

In both cases the absence of LVDS data has zero effect on anomaly detection.
A channel is only "new" if the reference has no statistics for it at all
(i.e. it never appeared in training data).

Config-driven normalisations (applied when include_trigger_config=True)
------------------------------------------------------------------------
Per-run MilliDAQ config files are parsed once per file and used exclusively
to transform observable features *before* scoring.  No new features are added;
the feature space size is identical regardless of whether config integration is
active.  This means the model never raises an alert because a config parameter
changed — it alerts only when observables are inconsistent with the run's own
config.

Three transformations (each gated by the corresponding variable being in
trigger_config_vars):

  1. Prescale normalisation (triggerBoard.prescale):
         triggerRate_bit{N} → raw_rate / prescale[N-1]   (physics rate)
     Runs with different prescale settings produce comparable trigger rates.
     triggerRate_tot and triggerCounts_tot are left unnormalised.

  2. Disabled trigger masking (triggerBoard.trigger):
         triggerRate_bit{N} → NaN for disabled trigger types.
     A zero rate from an inactive trigger is expected, not anomalous; NaN
     features are transparent to both the Welford reference and z-scoring.

  3. LVDS channel masking (triggerBoard.trigger_mask):
         All features for channels 2p and 2p+1 → NaN when LVDS pin p is masked.
     Masked channels do not contribute to the reference or anomaly score.
     Pin p covers digitizer channels 2p and 2p+1 (pins 0–47 → channels 0–95).

The DAQ config flag (include_daq_config) is accepted for API and tag-suffix
purposes but currently applies no transformation (no analytical normalisation
is available for per-channel thresholds without the full pulse-height spectrum).

Config flags and variable lists are stored in reference.npz and
training_metadata.json for bookkeeping; they do not affect the scoring logic.
"""

from __future__ import annotations

import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

from sklearn.ensemble import IsolationForest

from .features import extract_features, feature_columns
from .reference import ReferenceModel


class AnomalyDetector:

    def __init__(
        self,
        reference: ReferenceModel,
        z_threshold: float = 5.0,
        if_contamination: float = 0.05,
    ) -> None:
        self.reference = reference
        self.z_threshold = z_threshold
        self.if_contamination = if_contamination
        self._if_model: Optional[IsolationForest] = None
        self._use_trigger: bool              = getattr(reference, "_use_trigger",             True)
        self._use_lvds: bool                 = getattr(reference, "_use_lvds",                False)
        self._ignore_features: tuple         = getattr(reference, "_ignore_features",         ())
        self._include_trigger_config: bool   = getattr(reference, "_include_trigger_config",  False)
        self._trigger_config_vars: tuple     = getattr(reference, "_trigger_config_vars",     ())
        self._include_daq_config: bool       = getattr(reference, "_include_daq_config",      False)
        self._daq_config_vars: tuple         = getattr(reference, "_daq_config_vars",         ())
        self._run_configs_dir: str           = getattr(reference, "_run_configs_dir",         "")
        self._thresholds_json_path: str      = getattr(reference, "_thresholds_json_path",    "")
        self._feat_cols: list = feature_columns(
            use_trigger=self._use_trigger,
            use_lvds=self._use_lvds,
            ignore_features=self._ignore_features,
        )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train_isolation_forest(
        self,
        csv_files: list,
        max_samples: int = 50_000,
        features_cache: list = None,
    ) -> None:
        """
        Train an Isolation Forest on z-scored channel feature vectors from good data.

        csv_files      : explicit list of good Digitizer CSV file paths.
        features_cache : optional list of pre-computed feature DataFrames (one per
                         file, same order as csv_files) returned by build_reference().
                         When provided, files are not re-read from disk — halves I/O.

        Using z-scores (not raw values) makes the IF scale-invariant — channels
        with different baseline values are comparable, and the IF learns what
        "normal deviation patterns" look like rather than memorizing raw scales.

        max_samples caps the training set for the 10^6-file future: when the
        training corpus grows beyond that limit a random subsample is drawn,
        keeping training fast while maintaining representativeness.
        """
        z_vectors: list = []
        source = features_cache if features_cache is not None else None
        for i, f in enumerate(csv_files):
            features = source[i] if source is not None else extract_features(
                str(f),
                use_trigger=self._use_trigger,
                use_lvds=self._use_lvds,
                ignore_features=self._ignore_features,
                include_trigger_config=self._include_trigger_config,
                trigger_config_vars=self._trigger_config_vars,
                include_daq_config=self._include_daq_config,
                daq_config_vars=self._daq_config_vars,
                run_configs_dir=self._run_configs_dir,
                thresholds_json_path=self._thresholds_json_path,
            )
            z_df = self.reference.z_score(features)
            # Drop rows that are entirely NaN (channels not in the reference).
            # Fill any remaining NaN with 0 (= nominal z-score) so that channels
            # with missing optional features (e.g. no TriggerBoard file) are kept.
            z_df = z_df.dropna(how="all").fillna(0.0)
            if not z_df.empty:
                z_vectors.append(z_df.values)

        if not z_vectors:
            raise ValueError("No valid feature vectors found — csv_files list may be empty.")

        X = np.vstack(z_vectors)

        if len(X) > max_samples:
            rng = np.random.default_rng(42)
            idx = rng.choice(len(X), max_samples, replace=False)
            X = X[idx]

        self._if_model = IsolationForest(
            n_estimators=200,
            contamination=self.if_contamination,
            random_state=42,
            n_jobs=-1,
        )
        self._if_model.fit(X)
        print(f"  Isolation Forest trained on {len(X)} (channel × file) z-score vectors.")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def analyze_file(self, filepath: str) -> pd.DataFrame:
        """
        Analyze one Digitizer CSV file.

        Returns a DataFrame indexed by channel with columns:
          anomalous          — bool, True if flagged by either layer
          method             — which layer(s) triggered: "statistical", "isolation_forest",
                               "statistical+IF", "new_channel", "missing_channel", or "" (nominal)
          triggered_features — semicolon-separated feature names with |z| > threshold
          max_z              — largest absolute z-score across all features
          if_score           — Isolation Forest anomaly score (lower = more anomalous)

        Channel classification:
          new_channel     — channel appears in this file but has no reference statistics;
                            flagged because the reference cannot assess it.
          missing_channel — real channel known to the reference but entirely absent from
                            this file; flagged because it was active during training.
          (nominal / other) — known channels with absent optional data sources (e.g.
                            trigger_lvds_total when the LVDS file is missing) produce
                            all-NaN z-scores that do not trigger either layer; they are
                            silently treated as nominal.
        """
        features = extract_features(
            filepath,
            use_trigger=self._use_trigger,
            use_lvds=self._use_lvds,
            ignore_features=self._ignore_features,
            include_trigger_config=self._include_trigger_config,
            trigger_config_vars=self._trigger_config_vars,
            include_daq_config=self._include_daq_config,
            daq_config_vars=self._daq_config_vars,
            run_configs_dir=self._run_configs_dir,
            thresholds_json_path=self._thresholds_json_path,
        )
        if features.empty:
            import warnings
            warnings.warn(f"No events found in {filepath} — returning empty results.")
            return pd.DataFrame(columns=["anomalous", "method", "triggered_features",
                                         "max_z", "if_score"])

        z_df = self.reference.z_score(features)

        rows = []
        # Channels in the reference but absent from this file — completely silent
        present = set(features.index)
        for channel in self.reference.known_channels():
            if channel not in present:
                rows.append({
                    "channel": channel,
                    "stat_flag": True,
                    "if_flag": False,
                    "triggered_features": "missing_channel",
                    "max_z": np.nan,
                    "if_score": np.nan,
                    "anomalous": True,
                    "method": "missing_channel",
                })

        for channel in features.index:
            row: dict = {"channel": channel}

            z_row = z_df.loc[channel] if channel in z_df.index else None
            # A channel is "new" only when the reference has no statistics for it —
            # it never appeared in training data.  A known channel whose data source
            # was absent this run (e.g. trigger_lvds_total with no LVDS file) has
            # all-NaN z-scores but is NOT new: its absence is expected and benign.
            is_new = self.reference.get_stats(channel) is None

            # ---- Layer 1: statistical z-score ----
            if is_new:
                row["stat_flag"] = True   # unknown channel is inherently suspicious
                row["triggered_features"] = "new_channel"
                row["max_z"] = np.nan
            else:
                abs_z = z_row.abs()
                max_z = float(abs_z.max())
                triggered = abs_z[abs_z > self.z_threshold].index.tolist()
                row["stat_flag"] = bool(triggered)
                row["triggered_features"] = ";".join(triggered)
                row["max_z"] = round(max_z, 2)

            # ---- Layer 2: Isolation Forest ----
            if self._if_model is not None and not is_new:
                z_vec = z_row.fillna(0.0).to_numpy().reshape(1, -1)
                if_score = float(self._if_model.score_samples(z_vec)[0])
                if_flag = self._if_model.predict(z_vec)[0] == -1
                row["if_score"] = round(if_score, 4)
                row["if_flag"] = bool(if_flag)
            else:
                row["if_score"] = np.nan
                row["if_flag"] = False

            row["anomalous"] = row["stat_flag"] or row["if_flag"]

            if is_new:
                row["method"] = "new_channel"
            elif row["stat_flag"] and row["if_flag"]:
                row["method"] = "statistical+IF"
            elif row["stat_flag"]:
                row["method"] = "statistical"
            elif row["if_flag"]:
                row["method"] = "isolation_forest"
            else:
                row["method"] = ""

            rows.append(row)

        result = pd.DataFrame(rows).set_index("channel")
        return result[["anomalous", "method", "triggered_features", "max_z", "if_score"]]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            pickle.dump(
                {
                    "if_model": self._if_model,
                    "z_threshold": self.z_threshold,
                    "if_contamination": self.if_contamination,
                },
                fh,
            )

    @classmethod
    def load(cls, path: str, reference: ReferenceModel) -> "AnomalyDetector":
        with open(path, "rb") as fh:
            data = pickle.load(fh)
        det = cls(
            reference,
            z_threshold=data["z_threshold"],
            if_contamination=data["if_contamination"],
        )
        det._if_model = data["if_model"]
        return det
