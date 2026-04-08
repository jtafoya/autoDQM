"""
Reference model built from good data using Welford's online algorithm.

Stores per-channel, per-feature running statistics (count, mean, M2) that
can be updated incrementally — new good files can be added without reprocessing
the entire history. This is the scalability mechanism for >10^6 files.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple

from .features import extract_features, feature_columns


class ReferenceModel:
    """
    Per-channel Welford online statistics.

    Internal state per channel:
        count : int          — number of files seen
        mean  : np.ndarray   — running feature mean
        M2    : np.ndarray   — running sum of squared deviations (for variance)

    std is derived from M2 on demand: sqrt(M2 / count).
    """

    def __init__(self) -> None:
        self._state: dict = {}           # channel (int) -> {"count", "mean", "M2"}
        self._feat_cols: list = feature_columns()
        self._n_feats: int = len(self._feat_cols)

    # ------------------------------------------------------------------
    # Incremental update
    # ------------------------------------------------------------------

    def update(self, features: pd.DataFrame) -> None:
        """Incorporate one file's per-channel feature DataFrame into the reference."""
        for channel, row in features.iterrows():
            x = row[self._feat_cols].to_numpy(dtype=float)
            if channel not in self._state:
                self._state[channel] = {
                    "count": 0,
                    "mean": np.zeros(self._n_feats),
                    "M2": np.zeros(self._n_feats),
                }
            s = self._state[channel]
            s["count"] += 1
            delta = x - s["mean"]
            s["mean"] += delta / s["count"]
            s["M2"] += delta * (x - s["mean"])   # Welford step

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_stats(self, channel: int) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Return (mean, std) arrays for a channel.
        Returns None if the channel was never seen in good data.
        std is floored at 1e-6 to avoid division by zero.
        """
        if channel not in self._state:
            return None
        s = self._state[channel]
        mean = s["mean"].copy()
        if s["count"] > 1:
            std = np.sqrt(s["M2"] / s["count"])
        else:
            std = np.ones(self._n_feats)  # single sample → can't estimate std
        std = np.where(std < 1e-6, 1e-6, std)
        return mean, std

    def known_channels(self) -> list:
        return list(self._state.keys())

    def n_files(self, channel: int) -> int:
        """Number of training files that contained this channel."""
        return self._state.get(channel, {}).get("count", 0)

    # ------------------------------------------------------------------
    # Z-score computation
    # ------------------------------------------------------------------

    def z_score(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Compute z-scores for every (channel, feature) in a new file.

        Channels absent from the reference get all-NaN rows (flagged separately
        by the detector as "new_channel").
        """
        records = {}
        for channel, row in features.iterrows():
            stats = self.get_stats(channel)
            if stats is None:
                records[channel] = {f: np.nan for f in self._feat_cols}
            else:
                mean, std = stats
                x = row[self._feat_cols].to_numpy(dtype=float)
                z = (x - mean) / std
                records[channel] = dict(zip(self._feat_cols, z))
        return pd.DataFrame(records).T.rename_axis("channel")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        channels = list(self._state.keys())
        np.savez(
            path,
            channels=np.array(channels),
            counts=np.array([self._state[c]["count"] for c in channels]),
            means=np.array([self._state[c]["mean"] for c in channels]),
            M2s=np.array([self._state[c]["M2"] for c in channels]),
            feat_cols=np.array(self._feat_cols),
        )

    @classmethod
    def load(cls, path: str) -> "ReferenceModel":
        data = np.load(path, allow_pickle=True)
        model = cls()
        for i, ch in enumerate(data["channels"]):
            model._state[int(ch)] = {
                "count": int(data["counts"][i]),
                "mean": data["means"][i].copy(),
                "M2": data["M2s"][i].copy(),
            }
        return model


# ------------------------------------------------------------------
# Convenience builder
# ------------------------------------------------------------------

def build_reference(csv_files: list) -> ReferenceModel:
    """
    Build a fresh ReferenceModel from an explicit list of CSV file paths.

    csv_files : list of str or Path
    """
    model = ReferenceModel()
    if not csv_files:
        raise ValueError("csv_files list is empty — nothing to build a reference from.")
    for f in csv_files:
        print(f"  [{Path(f).name}] extracting features...")
        model.update(extract_features(str(f)))
    print(f"  Reference built: {len(csv_files)} file(s), {len(model.known_channels())} channels.")
    return model
