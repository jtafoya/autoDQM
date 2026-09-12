#!/usr/bin/env python3
"""Offline Phase 1 visualization using the frozen campaign's production z machinery."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
from unittest.mock import patch

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import yaml
from src.features import extract_features, PSEUDO_TRIGGER, PSEUDO_LVDS
from src.reference import ReferenceModel
from src.detector import AnomalyDetector
from src.plot import _channel_order
from src.run_list import parse_run_subrun

RUNS = (1620, 1640, 1642, 1702, 1703, 2126)
STUDY = HERE.parent / "study_20260906T044011Z_7ac63c5a"
CAMPAIGN = ROOT / "kb_scan_campaigns/kb_task1_runs1500_3000_juan_v1"
FLAGS = ("use_trigger", "use_lvds", "ignore_features", "include_trigger_config",
         "trigger_config_vars", "include_daq_config", "daq_config_vars", "run_configs_dir",
         "thresholds_json_path")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def deny_api_connections():
    original = socket.socket.connect

    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("This offline supplement blocks Python IP connections")
        return original(sock, address)

    socket.socket.connect = connect


def load_model():
    meta = read(CAMPAIGN / "campaign_metadata.json")
    spec = meta["model"]
    for name in ("reference", "detector"):
        assert sha(spec[name + "_path"]) == spec[name + "_sha256"], f"{name} artifact changed"
    for name in ("features", "reference", "detector", "plot"):
        source = f"isolation_forest/src/{name}.py"
        assert sha(ROOT / "src" / f"{name}.py") == meta["code_sha256"][source], f"{source} changed"
    ref = ReferenceModel.load(spec["reference_path"])
    detector = AnomalyDetector.load(spec["detector_path"], ref)
    expected = spec["training_metadata"]["effective_config"]
    assert detector.z_threshold == expected["z_threshold"]
    for name, value in spec["feature_flags"].items():
        assert getattr(detector, "_" + name) == value
    assert list(ref._feat_cols) == list(detector._feat_cols)
    return detector, meta


_WORKER_DETECTOR = None


def init_worker():
    global _WORKER_DETECTOR
    deny_api_connections()
    _WORKER_DETECTOR, _ = load_model()


def z_for_file(path, detector):
    # The same argument list as plot.plot_file and AnomalyDetector.analyze_file.
    features = extract_features(str(path), **{k: getattr(detector, "_" + k) for k in FLAGS})
    if features.empty:
        return features, pd.DataFrame(columns=detector.reference._feat_cols)
    return features, detector.reference.z_score(features)


def process_path(path):
    detector = _WORKER_DETECTOR
    started = time.monotonic()
    item = {"path": str(path), "subrun": parse_run_subrun(Path(path).name)[1]}
    if not Path(path).is_file():
        return item | {"status": "missing_file"}, None, []
    item["sha256"] = sha(path)
    try:
        features, z = z_for_file(path, detector)
        if features.empty:
            return item | {"status": "empty_file"}, None, []
        if np.isinf(z.to_numpy(dtype=float)).any():
            raise ValueError("infinite z value; refusing silently undefined denominator")
        item.update(status="valid" if np.isfinite(z.to_numpy(dtype=float)).any() else "no_defined_z",
                    seconds=round(time.monotonic() - started, 3))
        return item, z, list(features.index)
    except Exception as exc:
        return item | {"status": "read_error", "error": f"{type(exc).__name__}: {exc}"}, None, []


def discover(run):
    run_dir = CAMPAIGN / "runs" / f"run{run}"
    declared = [Path(x) for x in (run_dir / "input_paths.txt").read_text().splitlines() if x.strip()]
    all_paths = set(declared)
    for parent in {p.parent for p in declared}:
        all_paths.update(parent.glob(f"Digitizer_run{run}_subrun*.csv"))
    by_subrun = {}
    for path in all_paths:
        r, s = parse_run_subrun(path.name)
        assert r == run and s is not None
        if s in by_subrun and by_subrun[s] != path:
            raise ValueError(f"ambiguous duplicate run/subrun: {run}/{s}")
        by_subrun[s] = path
    log = pd.read_csv(run_dir / "anomaly_log.csv", dtype={"channel": str})
    logged_names = sorted(set(log.filename))
    for name in logged_names:
        r, s = parse_run_subrun(name)
        assert r == run
        if s not in by_subrun:
            by_subrun[s] = declared[0].parent / name
    return [by_subrun[s] for s in sorted(by_subrun)], log, len(declared)


def aggregate(cube, threshold):
    valid = np.isfinite(cube)
    denominator = valid.sum(axis=0)
    numerator = (valid & (np.abs(cube) > threshold)).sum(axis=0)
    maximum = np.max(np.where(valid, np.abs(cube), -np.inf), axis=0)
    maximum[denominator == 0] = np.nan
    frequency = np.divide(numerator, denominator, out=np.full(maximum.shape, np.nan), where=denominator > 0)
    return maximum, frequency, denominator, numerator


def compare_log(z, frame, threshold):
    """Compare current values against the existing frozen per-subrun report."""
    by_channel = frame.set_index("channel")
    failures = []
    for channel in z.index:
        values = z.loc[channel].abs()
        if str(channel) not in by_channel.index:
            failures.append(f"ch{channel}: absent from frozen log")
            continue
        old = by_channel.loc[str(channel)]
        maximum = values.max()
        expected_max = old.max_z
        if not ((pd.isna(maximum) and pd.isna(expected_max)) or
                (pd.notna(maximum) and pd.notna(expected_max) and np.isclose(round(float(maximum), 2), float(expected_max), rtol=0, atol=0.011))):
            failures.append(f"ch{channel}: max_z mismatch")
        expected_features = set(str(old.triggered_features).split(";")) if pd.notna(old.triggered_features) else set()
        actual = set(values.index[values > threshold])
        if expected_features not in ({"new_channel"}, {"missing_channel"}) and actual != expected_features:
            failures.append(f"ch{channel}: triggered_features mismatch")
    return failures


class StopAfterHeatmap(BaseException):
    pass


def validate_plot(path, detector, output):
    """Capture the actual production plot_file image array, not a reimplementation."""
    from src import plot
    import matplotlib.pyplot as plt
    features, z = z_for_file(path, detector)
    captured = {}

    def save(fig, dest, fmt="png"):
        if str(dest).endswith("_zscore_heatmap.png"):
            ax = fig.axes[0]
            matrix = np.ma.filled(ax.images[0].get_array(), np.nan)
            labels = [t.get_text() for t in ax.get_yticklabels()]
            channels = [int(s[2:]) if s.startswith("ch") else s for s in labels]
            expected = np.clip(z.reindex(index=channels, columns=detector.reference._feat_cols).abs().to_numpy(), 0, 50)
            np.testing.assert_allclose(matrix, expected, rtol=0, atol=0, equal_nan=True)
            fig.savefig(output / "canonical_subrun_zscore_heatmap.png", dpi=110)
            captured.update(subrun=str(path), matrix_equal=True,
                            cells_compared=int(matrix.size), maximum_absolute_difference=0.0,
                            note="Production plot clips at 50; run-level numeric matrices remain unclipped.")
            raise StopAfterHeatmap()

    try:
        with patch.object(plot, "_save", side_effect=save):
            plot.plot_file(str(path), detector, output)
    except StopAfterHeatmap:
        pass
    finally:
        plt.close("all")
    assert captured, "production heatmap was not reached"
    z.to_csv(output / "canonical_subrun_signed_z.csv", index_label="channel")
    return captured


def collect_run(run, detector, workers, validate=False):
    output = HERE / f"run{run}"
    output.mkdir(exist_ok=True)
    paths, log, declared_count = discover(run)
    print(f"run{run}: {len(paths)} subruns discovered; processing with {workers} workers", flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=workers, initializer=init_worker) as pool:
        for i, result in enumerate(pool.map(process_path, paths), 1):
            results.append(result)
            if i % 50 == 0 or i == len(paths):
                print(f"run{run}: {i}/{len(paths)}", flush=True)
    indices = set(detector.reference.known_channels())
    for item, z, present in results:
        indices.update(present)
    channels = _channel_order(indices, PSEUDO_TRIGGER, PSEUDO_LVDS)
    features = list(detector.reference._feat_cols)
    cube = np.full((len(paths), len(channels), len(features)), np.nan)
    presence = np.zeros((len(paths), len(channels)), dtype=bool)
    streaming_max = np.full(cube.shape[1:], -np.inf)
    streaming_n = np.zeros(cube.shape[1:], dtype=int)
    streaming_above = np.zeros(cube.shape[1:], dtype=int)
    log_errors = []
    log_compared = 0
    log_groups = dict(tuple(log.groupby("filename")))
    for i, (item, z, present) in enumerate(results):
        presence[i] = [channel in present for channel in channels]
        if z is not None:
            array = z.reindex(index=channels, columns=features).to_numpy(dtype=float)
            cube[i] = array
            valid = np.isfinite(array)
            streaming_max[valid] = np.maximum(streaming_max[valid], np.abs(array[valid]))
            streaming_n += valid
            streaming_above += valid & (np.abs(array) > detector.z_threshold)
            if Path(item["path"]).name in log_groups:
                failures = compare_log(z, log_groups[Path(item["path"]).name], detector.z_threshold)
                log_errors.extend({"subrun": item["subrun"], "error": f} for f in failures)
                log_compared += 1
    maximum, frequency, denominator, numerator = aggregate(cube, detector.z_threshold)
    streaming_max[streaming_n == 0] = np.nan
    np.testing.assert_allclose(maximum, streaming_max, rtol=0, atol=0, equal_nan=True)
    np.testing.assert_array_equal(denominator, streaming_n)
    np.testing.assert_array_equal(numerator, streaming_above)
    assert np.all((frequency[np.isfinite(frequency)] >= 0) & (frequency[np.isfinite(frequency)] <= 1))
    assert np.array_equal(np.isnan(maximum), denominator == 0)
    assert np.array_equal(np.isnan(frequency), denominator == 0)
    np.testing.assert_allclose(frequency[denominator > 0], streaming_above[denominator > 0] / streaming_n[denominator > 0], rtol=0, atol=0)
    for name, matrix in (("max_abs_z", maximum), ("anomaly_frequency", frequency),
                         ("valid_subrun_count", denominator), ("exceedance_count", numerator)):
        pd.DataFrame(matrix, index=channels, columns=features).to_csv(output / f"run{run}_matrix_{name}.csv", index_label="channel")
    np.savez_compressed(output / "subrun_z_matrices.npz", signed_z=cube,
                        channels=np.asarray(channels, dtype=str), features=np.asarray(features),
                        subruns=np.asarray([r[0]["subrun"] for r in results]), presence=presence)
    records = [r[0] for r in results]
    pd.DataFrame(records).to_csv(output / "subrun_coverage.csv", index=False)
    matrix_valid = np.isfinite(cube).any(axis=(1, 2))
    detector_valid = np.array([r[0]["status"] in ("valid", "no_defined_z") for r in results])
    observed_channel_count = presence[detector_valid].sum(axis=0)
    pd.DataFrame({"channel": channels, "subruns_present": observed_channel_count,
                  "subruns_absent": int(detector_valid.sum()) - observed_channel_count,
                  "detector_valid_subruns": int(detector_valid.sum())}).to_csv(output / "channel_coverage.csv", index=False)
    context = read(STUDY / f"run{run}/trial_1/context.json")
    context_coverage = {key: (re.search(r"Coverage: ([^.]+)", value).group(1)
                                if re.search(r"Coverage: ([^.]+)", value) else "not specified")
                        for key, value in context.items() if key != "daq_config"}
    meta = {"run": run, "z_threshold": detector.z_threshold, "threshold_operator": ">",
            "feature_flags": {k: getattr(detector, "_" + k) for k in FLAGS},
            "feature_order": features, "channel_order": channels,
            "declared_campaign_subruns": declared_count, "total_subruns": len(paths),
            "matrix_valid_subruns": int(matrix_valid.sum()), "detector_valid_subruns": int(detector_valid.sum()),
            "missing_or_no_data_subruns": [r[0] for r in results if r[0]["status"] != "valid"],
            "frozen_if_subruns": int(log.filename.nunique()), "saved_phase1_context_coverage": context_coverage,
            "aggregation_validation": "PASS: independent streaming versus stacked reduction, including per-cell denominators",
            "frozen_log_subruns_compared": log_compared, "frozen_log_comparison_errors": log_errors,
            "matrix_has_pseudochannels": bool(any(isinstance(x, str) for x in channels)),
            "api_calls": 0, "ground_truth_loaded": False}
    if validate:
        sample = next(Path(item["path"]) for item, z, present in results if item["status"] == "valid")
        validation = output / "validation"
        validation.mkdir(exist_ok=True)
        meta["canonical_plot_validation"] = validate_plot(sample, detector, validation)
    write(output / "metadata.json", meta)
    if log_errors:
        raise AssertionError(f"run{run}: frozen anomaly-log mismatch; inspect metadata.json")
    return meta


CHANNEL = re.compile(r"\b(?:channels?|ch)\s*(\d{1,2})(?:(?:\s*(?:/|,|and|&)\s*)(?:ch(?:annels?)?\s*)?\d{1,2})*(?!\d)", re.I)
CONTEXT_TERMS = {
    "trigger mask": r"\btrigger[- ]mask\b|\bmask(?:ed|ing)?\b",
    "configuration": r"\bconfig(?:uration)?(?:s)?\b",
    "missing-channel behavior": r"\bmissing[- ]channels?\b|\bchannels?\b[^.;]{0,55}\bmissing\b|\bchannel[- ](?:presence|disappearance|loss)\b",
    "readout failure/dropout (hypothesis or check)": r"\breadout\b[^.;]{0,60}\b(?:fault|failure|loss|dropout|disrupt|interrupt)|\b(?:fault|failure|loss|dropout|disrupt|interrupt)[^.;]{0,60}\breadout\b",
    "trigger rate": r"\btrigger(?:[- ]board)?[- ]rates?\b",
    "LVDS pin16": r"\b(?:LVDS\s+)?pin[- ]?16\b",
    "LVDS": r"\bLVDS\b",
    "board matching": r"\bboard[- ]matching\b",
    "restart (proposed or hypothesized)": r"\brestart(?:s|ed|ing)?\b",
}


def snippets(prediction):
    for field in ("category", "cause", "action", "reasoning_summary"):
        text = prediction[field]
        if field == "reasoning_summary":
            chunks = re.split(r"\b(OBSERVED|INFERRED|UNKNOWN|CONTRADICTING|DISCRIMINATING CHECKS)(?:/[^:]+)?:", text)
            if len(chunks) > 1:
                if chunks[0].strip():
                    yield field, "unscoped", chunks[0]
                for i in range(1, len(chunks), 2):
                    yield field, "observed" if chunks[i] == "OBSERVED" else "inference_or_unknown", chunks[i + 1]
                continue
        yield field, "recommended_check" if field == "action" else "hypothesis_or_unscoped", text


def extract_mentions(prediction, feature_names, trial):
    hits = []
    for field, scope, text in snippets(prediction):
        for sentence in re.split(r"(?<=[.!?;])\s+", text):
            historical = bool(re.search(r"\bruns?\s+\d{4}\b|\bhistorical\b", sentence, re.I))
            for match in CHANNEL.finditer(sentence):
                for ch in re.findall(r"\d+", match.group()):
                    hits.append(dict(kind="channel", item=str(int(ch)), channel=int(ch), feature="",
                                     trial=trial, field=field, scope=scope, historical_or_ambiguous=historical, quote=sentence))
            exact_features = []
            for feature in feature_names:
                if re.search(r"(?<![\w])" + re.escape(feature) + r"(?![\w])", sentence):
                    exact_features.append(feature)
                    hits.append(dict(kind="feature", item=feature, channel="", feature=feature,
                                     trial=trial, field=field, scope=scope, historical_or_ambiguous=historical, quote=sentence))
            for item, pattern in CONTEXT_TERMS.items():
                searchable = sentence.replace("_", " ") if field == "category" else sentence
                if re.search(pattern, searchable, re.I):
                    hits.append(dict(kind="context", item=item, channel="", feature="", trial=trial,
                                     field=field, scope=scope, historical_or_ambiguous=historical, quote=sentence))
            # Strict local syntax only. No channel x feature cross-product from co-occurrence.
            if scope == "observed" and not historical:
                for feature in exact_features:
                    patterns = [r"\b(?:channel|ch)\s*(\d{1,2})(?!\d)\s*(?:['’]s\s*)?(?:at\s+|with\s+)?" + re.escape(feature) + r"\b",
                                r"\b" + re.escape(feature) + r"\s+(?:on|for|in)\s+(?:channel|ch)\s*(\d{1,2})(?!\d)",
                                r"\b(?:channel|ch)\s*(\d{1,2})(?!\d)\s+(?:has|shows|exhibits|across)\s+"
                                r"(?:(?!\b(?:channels?|ch|but|whereas|while)\b)[^.;]){0,110}?\b" + re.escape(feature) + r"\b"]
                    for pattern in patterns:
                        for match in re.finditer(pattern, sentence, re.I):
                            ch = int(match.group(1))
                            hits.append(dict(kind="cell", item=f"ch{ch}:{feature}", channel=ch, feature=feature,
                                             trial=trial, field=field, scope=scope, historical_or_ambiguous=False, quote=sentence))
    return hits


def mentions_run(run, feature_names):
    hits = []
    predictions = []
    source_hashes = {}
    for trial in range(1, 6):
        path = STUDY / f"run{run}" / f"trial_{trial}"
        pred = read(path / "parsed_response.json")
        raw = read(path / "raw_response.json")
        output_text = "".join(c.get("text", "") for item in raw["output"] for c in item.get("content", []) if c.get("type") == "output_text")
        assert json.loads(output_text) == pred
        assert read(path / "metadata.json")["status"] == "completed"
        source_hashes[str(path / "parsed_response.json")] = sha(path / "parsed_response.json")
        source_hashes[str(path / "raw_response.json")] = sha(path / "raw_response.json")
        predictions.append(pred)
        hits.extend(extract_mentions(pred, feature_names, trial))
    frame = pd.DataFrame(hits)
    rows = []
    for (kind, item), group in frame.groupby(["kind", "item"], sort=False):
        target = group[~group.historical_or_ambiguous]
        observations = target[target.scope == "observed"]
        rows.append(dict(kind=kind, item=item, channel=group.iloc[0].channel, feature=group.iloc[0].feature,
                         llm_mention_count=int(target.trial.nunique()), observed_mention_count=int(observations.trial.nunique()),
                         all_text_mention_count=int(group.trial.nunique()),
                         target_trials=",".join(map(str, sorted(target.trial.unique()))),
                         rule="cell: exact direct syntax in target OBSERVED text; otherwise axis label/text only"))
    counts = pd.DataFrame(rows)
    assert counts.llm_mention_count.between(0, 5).all()
    output = HERE / f"run{run}"
    frame.to_csv(output / "llm_mention_quotes.csv", index=False)
    counts.to_csv(output / f"run{run}_llm_mentions.csv", index=False)
    write(output / "phase1_predictions.json", predictions)
    write(output / "phase1_source_hashes.json", source_hashes)
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("all", "collect", "render", "mentions"), default="all")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--runs", nargs="+", type=int, choices=RUNS, default=list(RUNS))
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("workers must be 1-4")
    deny_api_connections()
    detector, campaign_meta = load_model()
    source_paths = [ROOT / "benchmarks/novel/novel_manifest.yaml", ROOT / "benchmarks/novel/context_manifest.yaml"]
    source_paths += list(STUDY.rglob("*"))
    before = {str(p): sha(p) for p in source_paths if p.is_file()}
    if args.stage in ("all", "collect"):
        for run in args.runs:
            collect_run(run, detector, args.workers, validate=(run == 1640))
    if args.stage in ("all", "collect", "mentions"):
        for run in args.runs:
            mentions_run(run, detector.reference._feat_cols)
    if args.stage != "collect":
        from render_feature_matrices import render_all
        render_all(args.runs)
    assert before == {name: sha(name) for name in before}, "protected Phase 1 inputs changed"
    write(HERE / "provenance.json", {"campaign": str(CAMPAIGN), "phase1_study": str(STUDY),
                                    "model": campaign_meta["model"], "protected_source_hashes": before,
                                    "api_calls": 0, "python_ip_connections_blocked": True,
                                    "ground_truth_loaded": False})
    print("Offline supplement complete; API calls: 0", flush=True)


if __name__ == "__main__":
    main()
