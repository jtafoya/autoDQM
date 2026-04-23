"""
Run list parser and filename utilities.

Three functions are provided:

1. extract_run_number(path)
   Parse the run number from a Digitizer filename (e.g. "Digitizer_run1234_subrun5.csv"
   → 1234).  Returns None if the pattern is absent.  Used by the per-run apply mode
   (--apply-specific-run) and by the combine guard in combine.py.

2. resolve_run_list(list_file) — text-based run list
   A plain text file where each non-empty, non-comment line is a glob pattern
   that expands to one or more Digitizer CSV file paths.

   Example good_run_list.txt::

       # Nominal runs before the broken-base incident
       ../data/broken_base_BeforeIncident/Digitizer_*.csv

       # Runs after the fix was applied
       ../data/broken_base_AfterFix/Digitizer_run1644_subrun*.csv

   Lines starting with '#' and blank lines are ignored.
   Patterns are resolved relative to the current working directory.

3. resolve_full_sample(json_path, slab_dir, quality, ...) — full-sample mode
   Reads the goodRunsListSlab.json catalogue and builds file paths directly
   from the slab directory on EOS.  Requires a quality level to be specified
   (Loose, Medium, Tight, or All) and an optional fraction for sub-sampling
   the catalogue.  Prints catalogue-level counts (total entries, tags, quality
   breakdowns), post-quality-filter counts, and post-fraction counts.  The
   pre-filter unique-run total is intentionally omitted to avoid confusion
   with the run count actually used by the caller.
   "All" selects entries that pass at least one quality criterion (OR logic).
"""

import glob
import json
import random
import re
from collections import Counter
from pathlib import Path

# Column indices within each "data" row of goodRunsListSlab.json
_COL_RUN              = 0
_COL_FILE             = 1
_COL_GOOD_RUN_LOOSE   = 2
_COL_GOOD_RUN_MEDIUM  = 3
_COL_GOOD_RUN_TIGHT   = 4
_COL_GOOD_SINGLE_TRIG = 5
_COL_TAG              = 6

# Mapping from CLI quality name to catalogue column index.
# "All" is handled separately (OR across all three columns) and is not in this dict.
QUALITY_CHOICES: dict[str, int] = {
    "Loose":  _COL_GOOD_RUN_LOOSE,
    "Medium": _COL_GOOD_RUN_MEDIUM,
    "Tight":  _COL_GOOD_RUN_TIGHT,
}

# Full set of accepted quality values (includes the synthetic "All" option)
QUALITY_ALL_CHOICES: list[str] = [*QUALITY_CHOICES, "All"]


def extract_run_number(path: str) -> "int | None":
    """Extract the run number from a Digitizer filename, or None if not parseable."""
    m = re.search(r"run(\d+)", Path(path).name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def resolve_run_files(slab_dir: str, run: int) -> list:
    """
    Return all Digitizer CSV files on disk for a given run number.

    Scans <slab_dir>/<floor100>/ directly — not catalogue-filtered — so every
    subrun present on disk is returned, regardless of run quality.
    """
    subdir = (run // 100) * 100
    pattern = str(Path(slab_dir) / str(subdir) / f"Digitizer_run{run}_subrun*.csv")
    return sorted(glob.glob(pattern))


def resolve_run_list(list_file: str) -> list:
    """
    Parse a text run list file and return a sorted list of resolved file paths.

    Each line is treated as a glob pattern. Duplicates are removed while
    preserving order of first appearance.
    """
    list_path = Path(list_file)
    if not list_path.exists():
        raise FileNotFoundError(f"Run list not found: {list_file}")

    seen = set()
    paths = []

    with open(list_path) as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            matched = sorted(glob.glob(line))
            if not matched:
                print(f"  WARNING: no files matched pattern on line {lineno}: '{line}'")
            for p in matched:
                if p not in seen:
                    seen.add(p)
                    paths.append(p)

    return paths


def resolve_full_sample(
    json_path: str,
    slab_dir: str,
    quality: str,
    fraction: float = 1.0,
    seed: int = 42,
    print_stats: bool = True,
) -> list:
    """
    Build a list of Digitizer CSV paths from the goodRunsListSlab.json catalogue.

    Files are located under *slab_dir*, organised in sub-directories whose name
    is the floor-100 of the run number (e.g. run 1214 → <slab_dir>/1200/).
    The expected file name pattern is::

        Digitizer_run{run}_subrun{file}.csv

    Parameters
    ----------
    json_path : str
        Path to goodRunsListSlab.json.  The file must have a top-level "data"
        list with rows in column order:
        [run, file, goodRunLoose, goodRunMedium, goodRunTight,
         goodSingleTrigger, tag].
    slab_dir : str
        Root directory of the slab dataset (e.g.
        /eos/experiment/milliqan/run3_MilliMon/slab).
    quality : str
        Quality level to filter on.  Must be one of:
        "Loose", "Medium", "Tight", or "All".
        "All" selects entries passing at least one quality criterion (OR).
    fraction : float
        Fraction of the quality-filtered entries to use (0 < value ≤ 1).
        A random sub-sample is drawn when fraction < 1.
    seed : int
        Random seed for reproducible sub-sampling.
    print_stats : bool
        If False, suppress the quality-filter and fraction-sample counts
        (useful in the apply-specific-run path where those counts describe the
        full catalogue, not the single targeted run).

    Returns
    -------
    list[str]
        Resolved, existing file paths in run/subrun order.
    """
    if quality not in QUALITY_ALL_CHOICES:
        raise ValueError(
            f"Unknown quality '{quality}'. Must be one of: {QUALITY_ALL_CHOICES}"
        )
    if not (0 < fraction <= 1.0):
        raise ValueError(f"fraction must be in (0, 1]; got {fraction}")

    json_path_obj = Path(json_path)
    if not json_path_obj.exists():
        raise FileNotFoundError(f"Good-runs catalogue not found: {json_path}")

    with open(json_path_obj) as fh:
        catalogue = json.load(fh)

    all_rows = catalogue["data"]

    # ── Statistics ────────────────────────────────────────────────────────────
    if print_stats:
        total_entries = len(all_rows)
        tag_counts    = Counter(r[_COL_TAG] for r in all_rows)
        loose_count   = sum(1 for r in all_rows if r[_COL_GOOD_RUN_LOOSE])
        medium_count  = sum(1 for r in all_rows if r[_COL_GOOD_RUN_MEDIUM])
        tight_count   = sum(1 for r in all_rows if r[_COL_GOOD_RUN_TIGHT])

        print()
        print("  ── goodRunsListSlab.json statistics ────────────────────────")
        print(f"     Total entries (run+subrun pairs) : {total_entries:>8,}")
        print(f"     Tags                             : {dict(tag_counts)}")
        print(f"     Loose                            : {loose_count:>8,}")
        print(f"     Medium                           : {medium_count:>8,}")
        print(f"     Tight                            : {tight_count:>8,}")

    # ── Filter by quality ─────────────────────────────────────────────────────
    if quality == "All":
        # OR across all three quality columns
        filtered = [
            r for r in all_rows
            if r[_COL_GOOD_RUN_LOOSE] or r[_COL_GOOD_RUN_MEDIUM] or r[_COL_GOOD_RUN_TIGHT]
        ]
    else:
        quality_col = QUALITY_CHOICES[quality]
        filtered = [r for r in all_rows if r[quality_col]]

    if print_stats:
        filtered_runs = len(set(r[_COL_RUN] for r in filtered))
        print(f"  ── After quality filter ({quality})")
        print(f"     Matching entries                 : {len(filtered):>8,}")
        print(f"     Unique runs                      : {filtered_runs:>8,}")

    # ── Sub-sample by fraction ────────────────────────────────────────────────
    if fraction < 1.0:
        rng = random.Random(seed)
        n_sample = max(1, int(round(len(filtered) * fraction)))
        filtered = rng.sample(filtered, n_sample)
        if print_stats:
            sampled_runs = len(set(r[_COL_RUN] for r in filtered))
            print(f"  ── After fraction sub-sample (fraction={fraction}, seed={seed})")
            print(f"     Sampled entries                  : {len(filtered):>8,}")
            print(f"     Unique runs in sample            : {sampled_runs:>8,}")

    if print_stats:
        print()

    # ── Build and validate paths ──────────────────────────────────────────────
    slab_root = Path(slab_dir)
    paths     = []
    missing   = 0

    for row in sorted(filtered, key=lambda r: (r[_COL_RUN], r[_COL_FILE])):
        run     = row[_COL_RUN]
        subrun  = row[_COL_FILE]
        # tag is available here for future use: row[_COL_TAG]
        subdir  = (run // 100) * 100
        fpath   = slab_root / str(subdir) / f"Digitizer_run{run}_subrun{subrun}.csv"
        if fpath.exists():
            paths.append(str(fpath))
        else:
            missing += 1

    if missing:
        print(f"  WARNING: {missing} catalogue entr{'y' if missing == 1 else 'ies'} "
              f"had no matching file on disk and were skipped.")

    print(f"  {len(paths)} file(s) resolved from full sample "
          f"({quality}, fraction={fraction}).")

    return paths
