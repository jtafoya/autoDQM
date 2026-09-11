#!/usr/bin/env python3
"""Offline, deterministic all-file raw-data compression. Never reads old predictions."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import io
from pathlib import Path
import re
import shutil
import sys
import warnings
from unittest.mock import patch
import numpy as np
import pandas as pd
from common import HERE, ROOT, RUNS, RAW_ROOT, canonical, digest, sha, read, write, offline, novel_module, source_hashes

STATS = ['count', 'mean', 'std_population', 'min', 'q05', 'q25', 'median', 'q75', 'q95', 'max', 'zero_count', 'negative_count']
QUANTILES = [0, .05, .25, .5, .75, .95, 1]
GEOMETRY = ['layer', 'supermodule', 'row', 'column']
METHOD = {
    'version': 'raw_consistency_v1', 'raw_is_lossy_summary_not_original_rows': True,
    'coverage': 'Every matching CSV and every row. No top-channel, anomaly-only or random sampling.',
    'numeric_columns': 'All columns except event_id, channel and geometry; malformed numeric cells fail.',
    'moments': 'Finite-value pooled mean and population SD, weighted by finite row count.',
    'histograms': '32 shared per-metric asinh-spaced bins spanning the observed finite min/max across all channels. Exact counts in these bins, from a second full pass.',
    'subrun_distributions': 'Quantiles of subrun medians, NOT pooled-event quantiles. Detailed within-subrun quantiles retained in raw_detail.npz.',
    'time': 'Eight consecutive equal-file-count bins ordered by numeric subrun. Not elapsed time. Bin means weighted by finite row count.',
    'presence': 'Observed channel events / observed events in that subrun; not external trigger efficiency. Absent-channel occupancy is zero, other measurements are unavailable.',
    'missing': 'Nonfinite numeric cells counted, never replaced by zero. Absent subrun/channel measurements stay NaN in detail and null in JSON.',
    'precision': 'Prompt numeric summaries rounded to 6 significant figures; detail arrays retain float64.',
    'limitations': 'Not waveforms. Compression loses exact event order, arbitrary cross-variable correlations, within-bin changes, fine distribution shape and individual outliers beyond stated extrema. No supplied good raw reference: absolute values alone do not prove a fault.',
}


def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)): return [clean(v) for v in x]
    if isinstance(x, (int, np.integer)): return int(x)
    if isinstance(x, (float, np.floating)): return float(f'{x:.6g}') if np.isfinite(x) else None
    return x


def ranges(values):
    values = sorted(set(map(int, values)))
    out = []
    for n in values:
        if out and n == out[-1][1] + 1: out[-1][1] = n
        else: out.append([n, n])
    return out


def discover(run, root=RAW_ROOT):
    folder = root / str(run // 100 * 100)
    pattern = re.compile(rf'Digitizer_run{run}_subrun(\d+)\.csv$')
    files = [(int(pattern.fullmatch(p.name).group(1)), p) for p in folder.glob(f'Digitizer_run{run}_subrun*.csv') if pattern.fullmatch(p.name)]
    files.sort()
    if not files: raise ValueError(f'No readable raw inputs: {folder}, run {run}')
    if len(set(s for s, _ in files)) != len(files): raise ValueError('Duplicate numeric subrun IDs')
    return files


def load_raw(path, columns=None):
    body = path.read_bytes()
    import hashlib
    frame = pd.read_csv(io.BytesIO(body))
    if frame.empty: raise ValueError(f'Empty raw CSV: {path}')
    if columns is not None and list(frame.columns) != columns: raise ValueError(f'Column schema changed: {path}')
    if not {'event_id', 'channel', *GEOMETRY}.issubset(frame.columns): raise ValueError(f'Missing identifier/geometry columns: {path}')
    if frame[['event_id', 'channel']].isna().any().any(): raise ValueError(f'Missing event/channel ID: {path}')
    ch = pd.to_numeric(frame.channel, errors='raise')
    if not ((ch % 1 == 0) & ch.between(0, 95)).all(): raise ValueError(f'Unexpected channel: {path}')
    frame['channel'] = ch.astype(int)
    return frame, hashlib.sha256(body).hexdigest(), len(body)


def metric_stats(values):
    result = np.full((values.shape[1], len(STATS)), np.nan)
    valid = np.isfinite(values)
    a = np.where(valid, values, np.nan)
    n = valid.sum(axis=0)
    result[:, 0] = n
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        result[:, 1] = np.nanmean(a, axis=0)
        result[:, 2] = np.nanstd(a, axis=0)
        result[:, 3:10] = np.nanquantile(a, QUANTILES, axis=0).T
    result[:, 10] = ((a == 0) & valid).sum(axis=0)
    result[:, 11] = ((a < 0) & valid).sum(axis=0)
    return result


def pooled(a):
    n = np.nan_to_num(a[:, 0])
    total = int(n.sum())
    if not total: return {'n': 0, 'mean': None, 'std_population': None, 'min': None, 'max': None, 'zero_fraction': None, 'negative_fraction': None}
    ok = n > 0
    n, means, stds = n[ok], a[ok, 1], a[ok, 2]
    mean = np.sum(n * means) / total
    variance = np.sum(n * (stds ** 2 + (means - mean) ** 2)) / total
    return clean({'n': total, 'mean': mean, 'std_population': np.sqrt(variance),
                  'min': np.nanmin(a[:, 3]), 'max': np.nanmax(a[:, 9]),
                  'zero_fraction': np.nansum(a[:, 10]) / total,
                  'negative_fraction': np.nansum(a[:, 11]) / total})


def raw_summary(run, out, raw_root=RAW_ROOT):
    files = discover(run, raw_root)
    first, _, _ = load_raw(files[0][1])
    columns = list(first.columns)
    metrics = [c for c in columns if c not in ['event_id', 'channel', *GEOMETRY]]
    subruns = np.array([s for s, _ in files], dtype=int)
    stats = np.full((len(files), 96, len(metrics), len(STATS)), np.nan)
    events = np.zeros((len(files), 96), dtype=np.int64)
    rows = np.zeros_like(events)
    dead = np.zeros_like(events)
    total_events = np.zeros(len(files), dtype=np.int64)
    geometry = {c: {k: set() for k in GEOMETRY} for c in range(96)}
    inventory = []
    for i, (subrun, path) in enumerate(files):
        frame, h, size = load_raw(path, columns)
        frame[metrics] = frame[metrics].apply(pd.to_numeric, errors='raise')
        total_events[i] = frame.event_id.nunique()
        for c, g in frame.groupby('channel', sort=True):
            rows[i, c] = len(g)
            events[i, c] = g.event_id.nunique()
            dead[i, c] = g.loc[g.nPulses == 0, 'event_id'].nunique() if 'nPulses' in metrics else 0
            stats[i, c] = metric_stats(g[metrics].to_numpy(dtype=float))
            for k in GEOMETRY: geometry[c][k].update(map(str, g[k].dropna().unique()))
        inventory.append({'subrun': subrun, 'path': str(path), 'sha256': h, 'bytes': size,
                          'rows': len(frame), 'events': int(total_events[i]),
                          'duplicate_event_channel_rows': int(frame.duplicated(['event_id', 'channel']).sum())})
        if (i + 1) % 100 == 0: print(f'run {run}: statistics {i+1}/{len(files)}', flush=True)
    edges = []
    for m in range(len(metrics)):
        lo, hi = stats[:, :, m, 3], stats[:, :, m, 9]
        lo, hi = lo[np.isfinite(lo)], hi[np.isfinite(hi)]
        if not len(lo): edges.append(None); continue
        low, high = float(lo.min()), float(hi.max())
        if low == high:
            delta = max(abs(low) * .01, 1.)
            low, high = low - delta, high + delta
        edge = np.sinh(np.linspace(np.arcsinh(low), np.arcsinh(high), 33))
        edge[0], edge[-1] = low, high
        edges.append(edge)
    hist = np.zeros((96, len(metrics), 32), dtype=np.int64)
    for i, (_, path) in enumerate(files):
        frame, h, _ = load_raw(path, columns)
        if h != inventory[i]['sha256']: raise ValueError(f'Raw input changed between passes: {path}')
        for c, g in frame.groupby('channel', sort=True):
            for m, metric in enumerate(metrics):
                if edges[m] is None: continue
                vals = pd.to_numeric(g[metric], errors='raise').to_numpy(float)
                hist[c, m] += np.histogram(vals[np.isfinite(vals)], bins=edges[m])[0]
        if (i + 1) % 200 == 0: print(f'run {run}: distributions {i+1}/{len(files)}', flush=True)
    if discover(run, raw_root) != files: raise ValueError('Raw file inventory changed during preparation')
    bins = [b for b in np.array_split(np.arange(len(files)), 8) if len(b)]
    bin_ranges = [[int(subruns[b[0]]), int(subruns[b[-1]])] for b in bins]
    evidence = []
    for c in range(96):
        occupancy = events[:, c] / total_events
        evidence.append(clean({'id': f'P-{c:03}', 'kind': 'raw_presence', 'channel': c,
            'present_subruns': int((rows[:, c] > 0).sum()), 'total_subruns': len(files),
            'absent_subrun_ranges': ranges(subruns[rows[:, c] == 0]),
            'event_weighted_occupancy': events[:, c].sum() / total_events.sum(),
            'occupancy_quantiles': np.quantile(occupancy, QUANTILES),
            'time_bin_occupancy': [events[b, c].sum() / total_events[b].sum() for b in bins],
            'zero_pulse_event_fraction_when_present': dead[:, c].sum() / events[:, c].sum() if events[:, c].sum() else None,
            'geometry_values': {k: sorted(v) for k, v in geometry[c].items()}}))
        for m, metric in enumerate(metrics):
            a = stats[:, c, m]
            p = pooled(a)
            if hist[c, m].sum() != p['n']: raise ValueError('Histogram/finite-count reconciliation failed')
            valid = np.isfinite(a[:, 6])
            changes = np.abs(np.diff(a[:, 1]))
            step = int(np.nanargmax(changes)) if np.isfinite(changes).any() else None
            record = {'id': f'R-{c:03}-{m:02}', 'kind': 'raw_metric', 'channel': c, 'metric': metric,
                **p, 'nonfinite_count': int(rows[:, c].sum() - p['n']),
                'subrun_median_quantiles': np.quantile(a[valid, 6], QUANTILES) if valid.any() else [None]*7,
                'histogram_counts': hist[c, m],
                'time_bin_mean': [pooled(a[b])['mean'] for b in bins],
                'time_bin_valid_count': [pooled(a[b])['n'] for b in bins],
                'largest_adjacent_mean_change': None if step is None else {
                    'subruns': [int(subruns[step]), int(subruns[step+1])],
                    'means': [a[step, 1], a[step+1, 1]]}}
            evidence.append(clean(record))
    np.savez_compressed(out / 'raw_detail.npz', stats=stats, rows=rows, channel_events=events,
                        total_events=total_events, zero_pulse_events=dead, subruns=subruns,
                        channels=np.arange(96), metrics=metrics, statistic_names=STATS,
                        histograms=hist, histogram_edges=np.array([e if e is not None else np.full(33, np.nan) for e in edges]))
    meta = {'run': run, 'method': METHOD, 'files': inventory, 'file_count': len(files),
            'total_bytes': sum(x['bytes'] for x in inventory), 'total_rows': sum(x['rows'] for x in inventory),
            'columns': columns, 'metrics': metrics, 'subrun_ranges': ranges(subruns),
            'time_bin_subrun_ranges': bin_ranges, 'time_bin_file_counts': [len(b) for b in bins],
            'histogram_edges_by_metric': clean(dict(zip(metrics, edges))),
            'quantile_probabilities': QUANTILES, 'summary_directory': str(out.resolve())}
    write(out / 'raw_inventory.json', meta)
    return evidence, meta


def anomaly_summary(path, run, raw_subruns):
    frame = pd.read_csv(path, keep_default_na=False)
    matched = frame.filename.str.extract(r'Digitizer_run(\d+)_subrun(\d+)\.csv$')
    if matched.isna().any().any() or not (matched[0].astype(int) == run).all(): raise ValueError('Foreign/malformed anomaly filenames')
    frame['subrun'] = matched[1].astype(int)
    if set(frame.subrun) != set(raw_subruns): raise ValueError('Anomaly/raw subrun coverage differs')
    if frame.duplicated(['subrun', 'channel']).any(): raise ValueError('Duplicate anomaly subrun/channel rows')
    flags = frame.anomalous.astype(str).str.lower()
    if not flags.isin(['true', 'false']).all(): raise ValueError('Invalid anomaly flags')
    frame['bad'] = flags == 'true'
    records = []
    for ch, g in frame.groupby('channel', sort=True):
        z = pd.to_numeric(g.max_z, errors='coerce').to_numpy(float)
        scores = pd.to_numeric(g.if_score, errors='coerce').to_numpy(float)
        features = Counter()
        for value in g.loc[g.bad, 'triggered_features']:
            features.update(x.strip() for x in re.split(r'[;,]', str(value)) if x.strip())
        bad = g[g.bad]
        records.append(clean({'id': f'A-{int(ch):03}', 'kind': 'anomaly', 'channel': int(ch),
            'logged_subruns': len(g), 'anomalous_subruns': len(bad),
            'anomalous_subrun_ranges': ranges(bad.subrun),
            'method_counts': dict(sorted(Counter(bad.method).items())),
            'triggered_feature_counts': dict(sorted(features.items())),
            'max_z_quantiles': np.quantile(z[np.isfinite(z)], QUANTILES) if np.isfinite(z).any() else [None]*7,
            'if_score_quantiles': np.quantile(scores[np.isfinite(scores)], QUANTILES) if np.isfinite(scores).any() else [None]*7}))
    counts = frame.groupby('subrun').bad.sum()
    records.append({'id': 'A-ALL', 'kind': 'anomaly_overview', 'logged_rows': len(frame),
        'anomalous_rows': int(frame.bad.sum()), 'subruns': sorted(map(int, counts.index)),
        'anomalous_channel_count_by_subrun': list(map(int, counts)),
        'definition': 'All frozen log rows aggregated, no top-N selection; max_z is channel maximum, not a signed per-feature value. IF score follows frozen pipeline convention.'})
    return records


def prepare_run(args):
    run, bundle, raw_root = args
    offline()
    out = Path(bundle) / f'run{run}'
    out.mkdir(parents=True, exist_ok=False)
    novel = novel_module()
    manifest = novel.load_manifest(context_mode='full')
    kb = novel.resolve_path(manifest['production_kb'])
    baseline_hashes = source_hashes()
    baseline_hashes[str(kb)] = sha(kb)
    # Retain the established family-removal and provenance-redaction rules.
    with patch.object(novel.contextual, 'MAX_SECTION_CHARS', 1_000_000):
        case = novel.prepare_case(manifest, run, novel.recognition.load_kb(kb), context_mode='full')
    novel.assert_case_safe(case)
    raw_records, meta = raw_summary(run, out, Path(raw_root))
    anomaly_path = Path(case.target_evidence_source)
    before = sha(anomaly_path)
    anomaly_records = anomaly_summary(anomaly_path, run, [f['subrun'] for f in meta['files']])
    shutil.copyfile(anomaly_path, out / 'anomaly_log.csv')
    if before != sha(out / 'anomaly_log.csv') or before != sha(anomaly_path): raise ValueError('Anomaly source changed')
    records = anomaly_records[:]
    context = {'trigger': case.trigger_summary, 'lvds': case.lvds_summary, 'daq_config': case.daq_config_summary}
    for component, text in context.items():
        for i, line in enumerate(text.splitlines()):
            if line.strip(): records.append({'id': f'C-{component}-{i:03}', 'kind': 'context', 'component': component, 'text': line})
    for entry in case.filtered_kb:
        historical_run = novel.recognition.singleton_run(entry)
        records.append({'id': f'H-{historical_run}', 'kind': 'historical_analogy', 'source_run': historical_run, 'entry': entry})
    records += raw_records
    if len({r['id'] for r in records}) != len(records): raise ValueError('Duplicate evidence IDs')
    # Paths/run identity retained in local provenance, not detector observations sent to LLM.
    prompt_header = {'method': METHOD, 'case_id': 'CASE_TARGET', 'raw_file_count': meta['file_count'],
        'raw_total_rows': meta['total_rows'], 'raw_subrun_ranges': meta['subrun_ranges'],
        'time_bin_subrun_ranges': meta['time_bin_subrun_ranges'], 'time_bin_file_counts': meta['time_bin_file_counts'],
        'histogram_edges_by_metric': meta['histogram_edges_by_metric'], 'quantile_probabilities': QUANTILES,
        'hardware_mapping_note': 'Trigger mask indices are physical pins, not digitizer channels. Existing mapping skips physical pins 32-39 and 43, then consecutive LVDS pin l maps to digitizer 2*l and 2*l+1. A mask index number must not be equated to the same digitizer channel number.',
        'record_id_legend': 'A: complete aggregate anomaly log; C: context including unavailable evidence; H: filtered historical KB (analogy, not current observation); P: raw presence; R: raw numeric metric.',
        'context_coverage_warning': 'Each telemetry source has its own coverage. Do not extrapolate a partial-run absence of anomalies to the whole run.'}
    write(out / 'summary_header.json', prompt_header)
    (out / 'evidence.jsonl').write_text(''.join(canonical(r)+'\n' for r in records))
    write(out / 'filtered_kb.json', case.filtered_kb)
    write(out / 'context.json', context)
    write(out / 'anomaly_summary.json', anomaly_records)
    context_hashes = {p: sha(p) for paths in case.context_source_paths.values() for p in paths}
    sources = {**baseline_hashes, str(anomaly_path): before, **context_hashes}
    from common import verify_files
    verify_files(sources)
    artifacts = {str(p.resolve()): sha(p) for p in out.iterdir() if p.is_file()}
    write(out / 'manifest.json', {'run': run, 'status': 'prepared', 'source_hashes': sources,
        'artifact_hashes': artifacts, 'raw_file_set_sha256': digest(meta['files']),
        'excluded_runs': case.exclude_runs, 'visible_historical_runs': case.visible_historical_runs,
        'production_system_prompt': case.system_prompt,
        'input_method': METHOD, 'ground_truth_in_model_input': False})
    print(f'run {run}: prepared {meta["file_count"]} files; {len(records)} evidence records', flush=True)
    return {'run': run, 'directory': str(out.resolve()), 'file_count': meta['file_count'], 'total_rows': meta['total_rows'], 'manifest_sha256': sha(out / 'manifest.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', nargs='+', type=int, choices=RUNS, default=RUNS)
    parser.add_argument('--workers', type=int, choices=[1, 2], default=2)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    offline()
    bundle = args.output or HERE / 'inputs' / datetime.now(timezone.utc).strftime('bundle_%Y%m%dT%H%M%SZ')
    bundle = bundle.resolve()
    bundle.mkdir(parents=True, exist_ok=False)
    tasks = [(run, str(bundle), str(RAW_ROOT)) for run in args.runs]
    if args.workers == 1: results = [prepare_run(a) for a in tasks]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool: results = list(pool.map(prepare_run, tasks))
    write(bundle / 'bundle.json', {'status': 'prepared', 'runs': results, 'source_hashes': source_hashes()})
    print(f'Inputs: {bundle}', flush=True)


if __name__ == '__main__': main()
