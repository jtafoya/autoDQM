"""
Run list parser.

A run list is a plain text file where each non-empty, non-comment line is a
glob pattern that expands to one or more Digitizer CSV file paths.

Example good_run_list.txt:
    # Nominal runs before the broken-base incident
    ../data/broken_base_BeforeIncident/Digitizer_*.csv

    # Runs after the fix was applied
    ../data/broken_base_AfterFix/Digitizer_run1644_subrun*.csv
    ../data/noisy_channel__AfterFix/Digitizer_*.csv

Lines starting with '#' and blank lines are ignored.
Patterns are resolved relative to the current working directory.
"""

import glob
from pathlib import Path


def resolve_run_list(list_file: str) -> list:
    """
    Parse a run list file and return a sorted list of resolved file paths.

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
