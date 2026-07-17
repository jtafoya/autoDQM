#!/usr/bin/env python3
"""Generate deterministic per-run Apply manifests from the training good list."""

from __future__ import annotations

import glob
import os
import random
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


ISOLATION_FOREST_DIR = Path(
    "/afs/cern.ch/user/p/pengy/autoDQM/isolation_forest"
)
GOOD_LIST = Path(
    "/afs/cern.ch/user/p/pengy/autoDQM/data/good_run_list_TRAINING.txt"
)
RUN_MANIFEST = ISOLATION_FOREST_DIR / "condor/apply_good_training_runs.txt"
SAMPLED_TSV = (
    ISOLATION_FOREST_DIR
    / "condor/apply_good_training_sampled_paths_seed42_frac40.tsv"
)
SEED = 42
FRACTION = 0.4


def _atomic_write(path: Path, text: str) -> None:
    """Atomically replace *path* with UTF-8 *text* on the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(path)


def _patterns() -> list[tuple[int, str]]:
    """Return non-empty, non-comment run-list patterns with line numbers."""
    patterns: list[tuple[int, str]] = []
    for lineno, raw in enumerate(GOOD_LIST.read_text().splitlines(), start=1):
        pattern = raw.strip()
        if pattern and not pattern.startswith("#"):
            patterns.append((lineno, pattern))
    return patterns


def main() -> None:
    """Expand the training good list and freeze a per-run 40% sample."""
    if not GOOD_LIST.is_file():
        raise FileNotFoundError(f"Good run list not found: {GOOD_LIST}")

    os.chdir(ISOLATION_FOREST_DIR)
    sys.path.insert(0, str(ISOLATION_FOREST_DIR))

    patterns = _patterns()
    unmatched = [
        (lineno, pattern)
        for lineno, pattern in patterns
        if not glob.glob(pattern)
    ]
    for lineno, pattern in unmatched:
        print(
            f"WARNING: unmatched run-list pattern on line {lineno}: {pattern}"
        )

    from src.run_list import (
        extract_run_number,
        resolve_run_list,
        run_subrun_sort_key,
    )

    resolved = resolve_run_list(str(GOOD_LIST))
    absolute_paths = list(
        dict.fromkeys(str(Path(path).resolve()) for path in resolved)
    )
    if not absolute_paths:
        raise RuntimeError("The good run list expanded to zero files")

    grouped: dict[int, list[str]] = defaultdict(list)
    for path in absolute_paths:
        path_obj = Path(path)
        if not path_obj.is_absolute():
            raise RuntimeError(f"Resolved path is not absolute: {path}")
        if not path_obj.is_file():
            raise FileNotFoundError(f"Resolved CSV does not exist: {path}")
        run = extract_run_number(path)
        if run is None:
            raise RuntimeError(f"Could not parse run number from: {path}")
        grouped[run].append(path)

    runs = sorted(grouped)
    sampled_rows: list[tuple[int, str]] = []
    statistics: list[tuple[int, int, int]] = []
    for run in runs:
        population = sorted(grouped[run], key=run_subrun_sort_key)
        n_selected = max(1, int(round(len(population) * FRACTION)))
        rng = random.Random(SEED)
        selected = rng.sample(population, n_selected)
        selected = sorted(selected, key=run_subrun_sort_key)
        sampled_rows.extend((run, path) for path in selected)
        statistics.append((run, len(population), len(selected)))

    if len({path for _, path in sampled_rows}) != len(sampled_rows):
        raise RuntimeError("Duplicate paths found in sampled output")

    run_text = "".join(f"{run}\n" for run in runs)
    tsv_text = "".join(f"{run}\t{path}\n" for run, path in sampled_rows)
    _atomic_write(RUN_MANIFEST, run_text)
    _atomic_write(SAMPLED_TSV, tsv_text)

    print(f"PATTERN_COUNT={len(patterns)}")
    print(f"MATCHED_PATTERN_COUNT={len(patterns) - len(unmatched)}")
    print(f"UNMATCHED_PATTERN_COUNT={len(unmatched)}")
    print(f"EXPANDED_CSV_COUNT={len(absolute_paths)}")
    print(f"UNIQUE_RUN_COUNT={len(runs)}")
    print(f"SELECTED_CSV_COUNT={len(sampled_rows)}")
    print("RUN\ttotal\tselected\tselected/total")
    for run, total, selected in statistics:
        print(f"{run}\t{total}\t{selected}\t{selected / total:.6f}")


if __name__ == "__main__":
    main()
