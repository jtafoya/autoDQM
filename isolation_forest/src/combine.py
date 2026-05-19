"""
Combine per-run apply outputs produced by --apply-specific-run into a single
log file suitable for global reporting and plots.

Typical workflow
----------------
1. Train once:
       python -m src.pipeline --train-goodRunList --skip-apply ...

2. Apply per run (e.g. as Condor array jobs):
       python -m src.pipeline --train-goodRunList --skip-train --apply-specific-run 1234

   Each job writes  logs/<tag>/<tag>_run<N>.csv  and  logs/<tag>/<tag>_run<N>_paths.txt.

3. Combine:
       python -m src.pipeline --combine-specific-run-outputs '*'
       python -m src.pipeline --combine-specific-run-outputs '100?'  # runs 1000-1009

   Writes logs/<tag>.csv (and the companion _paths.txt) from all matched
   per-run files.  The combined log's mtime is used by the guard to decide
   which per-run files are still uncombined.

4. Global plots / report (no --apply-specific-run):
       python -m src.pipeline --train-goodRunList --skip-train --skip-apply
"""

import sys
from pathlib import Path


def _error_uncombined(files: list, tag: str) -> None:
    files_str = "\n".join(f"  {f}" for f in files)
    print(
        f"ERROR: {len(files)} uncombined per-run output(s) exist for tag '{tag}':\n"
        f"{files_str}\n\n"
        f"Combine them first, then re-run the pipeline:\n"
        f"  python -m src.pipeline --combine-specific-run-outputs '*' [other flags]\n"
        f"(Use a wildcard to select which per-run outputs to include.)",
        file=sys.stderr,
    )
    sys.exit(1)


def check_no_uncombined_run_outputs(logs_dir: Path, tag: str) -> None:
    """
    Exit with an error if per-run output files exist that are newer than the
    combined log.  A per-run file is considered uncombined when:
      - no combined log <tag>.csv exists yet, OR
      - the per-run file was modified after the combined log was last written.

    Call this in the global pipeline path (i.e. when --apply-specific-run is
    NOT set) before running any step, so the user is forced to combine first.
    """
    run_files = sorted((logs_dir / tag).glob(f"{tag}_run*.csv"))
    if not run_files:
        return
    combined_log = logs_dir / f"{tag}.csv"
    if not combined_log.exists():
        _error_uncombined(run_files, tag)
    combined_mtime = combined_log.stat().st_mtime
    newer = [f for f in run_files if f.stat().st_mtime > combined_mtime]
    if newer:
        _error_uncombined(newer, tag)


def step_combine_specific_runs(pattern: str, logs_dir: Path, tag: str) -> None:
    """
    Combine per-run CSV files matching <tag>_run<pattern>.csv into <tag>.csv.

    PATTERN is a shell wildcard applied to the run-number portion of the
    filename (e.g. '*' for all runs, '100?' for runs 1000-1009).  Files
    present on disk that do not match are ignored; files referenced by the
    pattern but absent on disk are silently skipped.

    Also merges the companion _paths.txt caches so subsequent plot steps can
    locate the original EOS files.
    """
    import fnmatch
    import pandas as pd

    print(f"\n{'='*60}")
    print("  COMBINE SPECIFIC RUN OUTPUTS")
    print(f"{'='*60}\n")

    prefix = f"{tag}_run"
    all_run_files = sorted((logs_dir / tag).glob(f"{prefix}*.csv"))
    matched = [
        f for f in all_run_files
        if fnmatch.fnmatch(f.stem[len(prefix):], pattern)
    ]

    if not matched:
        print(f"  No files matching '{prefix}{pattern}.csv' found in {logs_dir}.")
        print("  Nothing to combine.")
        sys.exit(0)

    print(f"  {len(matched)} file(s) matched (pattern='{pattern}'):")
    for f in matched:
        print(f"    {f.name}")

    dfs = []
    for f in matched:
        try:
            dfs.append(pd.read_csv(f))
        except Exception as exc:
            print(f"  WARNING: skipping {f.name} — {exc}", file=sys.stderr)

    if not dfs:
        print("ERROR: no readable data found in matched files.", file=sys.stderr)
        sys.exit(1)

    combined = pd.concat(dfs, ignore_index=True)
    out_log = logs_dir / f"{tag}.csv"
    combined.to_csv(out_log, index=False)
    n_files = combined["filename"].nunique() if "filename" in combined.columns else "?"
    print(f"\n  Combined log → {out_log}")
    print(f"  {len(combined)} rows across {n_files} file(s)")

    # Merge companion path caches (deduplicate, preserve order)
    seen_paths: set = set()
    merged_paths: list = []
    for f in matched:
        cache = f.parent / (f.stem + "_paths.txt")
        if cache.exists():
            for line in cache.read_text().splitlines():
                if line.strip() and line not in seen_paths:
                    seen_paths.add(line)
                    merged_paths.append(line)
    if merged_paths:
        out_cache = logs_dir / f"{tag}_paths.txt"
        out_cache.write_text("\n".join(merged_paths))
        print(f"  Path cache  → {out_cache}  ({len(merged_paths)} entries)")
