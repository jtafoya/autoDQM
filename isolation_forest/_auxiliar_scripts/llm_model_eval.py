#!/usr/bin/env python3
"""
llm_model_eval.py — compare LLM models on the alert-categorization task using
elog-labelled runs from the knowledge base as ground truth.

For every KB run found in the supplied anomaly logs, the script replays the
canonical alert logic, picks up to --per-run alerted subruns, and asks each
model to categorize them with the SAME prompt src/llm.py builds in production
— with one crucial difference: the tested run's own KB entry is REMOVED from
the prompt (leave-one-out), so the model must match the anomaly signature to a
*different* run's case instead of trivially string-matching the run number.

Three case types, scored separately:
  matchable    the held-out run's category has a sibling entry in the KB —
               expect the correct category via the sibling. Core accuracy metric.
  unmatchable  the category has no sibling — the honest answer is low
               confidence / no good match. Scores calibration, not recall.
  control      (--controls N) no hold-out; sanity check, should be ~100%.

Usage (from isolation_forest/, ANTHROPIC_API_KEY in the environment):
    python3 _auxiliar_scripts/llm_model_eval.py \
        --kb  /path/to/llm_knowledge_base.yaml \
        --log /path/to/combined_or_per_run_log.csv [--log ...] \
        --snapshot-log /path/to/kb_snapshot_log.csv \
        [--models claude-opus-5,claude-sonnet-5,claude-haiku-4-5] \
        [--per-run 2] [--controls 2] [--max-cases 15] [--dry-run] \
        [--out-json eval_results.json]

--dry-run builds every prompt and prints the case table without calling any
API — use it to verify the test set (and cost) before spending tokens.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from src.llm import (  # noqa: E402
    _SYSTEM, _TASK, _call_api,
    _format_current_alert, _format_historical_case, _historical_snapshot,
)
from src.plot import _compute_persistence_status  # noqa: E402
from src.run_list import parse_run_subrun         # noqa: E402

# Baseline alert parameters (match the production config).
PERSIST_N, CONSEC, BULK_N, Z_EXTREME = 2, 5, 5, 15.0


def load_logs(paths: list) -> pd.DataFrame:
    frames = []
    for p in paths:
        df = pd.read_csv(p, low_memory=False)
        df["anomalous"] = (df["anomalous"]
                           .map({True: True, False: False, "True": True, "False": False,
                                 "true": True, "false": False})
                           .fillna(False).astype(bool))
        df["max_z"] = pd.to_numeric(df["max_z"], errors="coerce")
        df["if_score"] = pd.to_numeric(df["if_score"], errors="coerce")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    parsed = df["filename"].apply(lambda f: pd.Series(parse_run_subrun(f), index=["run", "subrun"]))
    df = pd.concat([df, parsed], axis=1).dropna(subset=["run"])
    df["run"] = df["run"].astype(int)
    return df


def alert_reasons_for(rows: pd.DataFrame, n_persistent: int) -> list:
    """Reconstruct monitor-style alert reason strings from a subrun's rows."""
    reasons = []
    if n_persistent >= PERSIST_N:
        reasons.append(f"{n_persistent} persistent anomalous channel(s)")
    n_bad = rows["channel"].nunique()
    if BULK_N and n_bad >= BULK_N:
        reasons.append(f"{n_bad} anomalous ch  [bulk >={BULK_N}]")
    zmax = rows["max_z"].max()
    if Z_EXTREME and pd.notna(zmax) and zmax >= Z_EXTREME:
        ch = rows.loc[rows["max_z"].idxmax(), "channel"]
        reasons.append(f"extreme z={zmax:.1f} on ch{ch}")
    return reasons or ["alert"]


def build_prompt(run: int, subrun: int, reasons: list, anom_df: pd.DataFrame,
                 kb_entries: list, snapshot_log: str) -> str:
    current = _format_current_alert(run, subrun, reasons, anom_df)
    cases = [
        _format_historical_case(e, _historical_snapshot(snapshot_log, e["run"]))
        for e in kb_entries
    ]
    return ("## Current alert\n\n" + current
            + "\n\n---\n\n## Historical reference cases\n\n"
            + "\n\n".join(cases) + _TASK)


def parse_response(raw: str) -> dict:
    """Parse the model's JSON; tolerate markdown fences / surrounding prose."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"parse_error": True, "raw": raw[:300]}


def score_case(case: dict, resp: dict) -> dict:
    cands = resp.get("candidates") or []
    top = cands[0] if cands else {}
    top_cat = str(top.get("category", "")).strip().lower()
    expected = case["expected_category"].strip().lower()
    out = {"parse_ok": "parse_error" not in resp, "top_category": top_cat or None,
           "confidence": top.get("confidence"), "matched_runs": top.get("matched_runs", [])}
    if case["mode"] == "unmatchable":
        # Honest = no confident wrong assertion: empty candidates, low confidence,
        # or an explicit unknown/no-match category.
        wrong_confident = (bool(top) and top_cat not in ("", "unknown", "none", "no_match")
                          and top_cat != expected
                          and str(top.get("confidence", "")).lower() in ("high", "medium"))
        out["correct"] = not wrong_confident
    else:
        out["correct"] = top_cat == expected
        if case["mode"] == "matchable":
            sibs = set(case["sibling_runs"])
            out["matched_sibling"] = bool(sibs & {int(r) for r in out["matched_runs"]
                                                  if str(r).isdigit() or isinstance(r, int)})
    return out


def main() -> None:
    # Line-buffer stdout so progress streams through pipes/tee (API calls are
    # minutes apart — block buffering makes the run look frozen).
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--kb", required=True)
    ap.add_argument("--log", action="append", required=True,
                    help="anomaly log CSV containing KB runs (repeatable)")
    ap.add_argument("--snapshot-log", required=True,
                    help="historical log used for KB snapshot injection")
    ap.add_argument("--models", default="claude-opus-5,claude-sonnet-5,claude-haiku-4-5")
    ap.add_argument("--per-run", type=int, default=2)
    ap.add_argument("--controls", type=int, default=2)
    ap.add_argument("--max-cases", type=int, default=15)
    ap.add_argument("--provider", default="anthropic")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-json", default="llm_model_eval_results.json")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()][:3]
    kb = [e for e in (yaml.safe_load(Path(args.kb).read_text()) or [])
          if isinstance(e, dict) and isinstance(e.get("run"), int)]
    by_cat: dict = defaultdict(list)
    for e in kb:
        by_cat[str(e.get("category", "")).strip().lower()].append(e["run"])
    print(f"KB: {len(kb)} valid entries, {len(by_cat)} categories")
    for cat, runs in sorted(by_cat.items()):
        tag = "" if len(runs) > 1 else "   (singleton — held-out cases become 'unmatchable')"
        print(f"  {cat:<24} runs={runs}{tag}")

    df = load_logs(args.log)
    kb_runs_in_logs = sorted(set(e["run"] for e in kb) & set(df["run"].unique()))
    print(f"\nKB runs present in supplied logs: {kb_runs_in_logs}")

    # Build test cases: replay per run, take the first --per-run alerted subruns.
    cases = []
    for run in kb_runs_in_logs:
        entry = next(e for e in kb if e["run"] == run)
        expected = str(entry.get("category", "")).strip()
        run_df = df[df["run"] == run]
        status = _compute_persistence_status(
            run_df, file_alert_n_channels=PERSIST_N, alert_consecutive_n=CONSEC,
            single_file_alert_n_channels=BULK_N, single_file_alert_max_z=Z_EXTREME)
        alerted = status[status.status == "alert"].head(args.per_run)
        sibs = [r for r in by_cat[expected.lower()] if r != run]
        for _, srow in alerted.iterrows():
            rows = run_df[(run_df.filename == srow.filename) & run_df.anomalous]
            if rows.empty:
                continue
            anom_df = rows.set_index("channel")[["max_z", "if_score", "triggered_features"]]
            cases.append({
                "run": run, "subrun": int(srow.subrun), "filename": srow.filename,
                "expected_category": expected,
                "mode": "matchable" if sibs else "unmatchable",
                "sibling_runs": sibs,
                "reasons": alert_reasons_for(rows, int(srow.n_persistent)),
                "anom_df": anom_df,
            })
    cases = cases[:args.max_cases]
    for c in cases[:args.controls]:
        cases.append({**c, "mode": "control"})

    print(f"\nTest cases: {len(cases)} "
          f"({Counter(c['mode'] for c in cases)}) × {len(models)} models "
          f"= {len(cases) * len(models)} API calls")
    for c in cases:
        print(f"  run{c['run']}/sub{c['subrun']:<5} {c['mode']:<12} expect={c['expected_category']}")
    if args.dry_run:
        p = build_prompt(cases[0]["run"], cases[0]["subrun"], cases[0]["reasons"],
                         cases[0]["anom_df"],
                         [e for e in kb if e["run"] != cases[0]["run"]],
                         args.snapshot_log) if cases else ""
        print(f"\n[dry-run] first prompt: {len(p):,} chars (~{len(p)//4:,} tokens); no API calls made.")
        return

    results = []
    for model in models:
        print(f"\n── {model} ──────────────────────────────────────────")
        for c in cases:
            holdout_kb = kb if c["mode"] == "control" else [e for e in kb if e["run"] != c["run"]]
            prompt = build_prompt(c["run"], c["subrun"], c["reasons"], c["anom_df"],
                                  holdout_kb, args.snapshot_log)
            t0 = time.monotonic()
            try:
                raw = _call_api(_SYSTEM, prompt, model, args.provider)
                resp = parse_response(raw)
            except Exception as exc:
                resp = {"parse_error": True, "raw": f"API error: {exc}"}
            dt = time.monotonic() - t0
            s = score_case(c, resp)
            results.append({"model": model, "run": c["run"], "subrun": c["subrun"],
                            "mode": c["mode"], "expected": c["expected_category"],
                            "latency_s": round(dt, 1), **s})
            mark = "OK " if s["correct"] else "MISS"
            print(f"  [{mark}] run{c['run']}/sub{c['subrun']} {c['mode']:<12} "
                  f"expect={c['expected_category']:<22} got={s['top_category']} "
                  f"({s['confidence']}) {dt:.0f}s")

    print("\n══ SUMMARY ═══════════════════════════════════════════")
    print(f"{'model':<22} {'matchable':>10} {'honesty':>8} {'control':>8} "
          f"{'parse':>6} {'median s':>9}")
    rows = pd.DataFrame(results)
    for model in models:
        r = rows[rows.model == model]
        def rate(mode):
            m = r[r["mode"] == mode]
            return f"{int(m.correct.sum())}/{len(m)}" if len(m) else "—"
        lat = r.latency_s.median()
        print(f"{model:<22} {rate('matchable'):>10} {rate('unmatchable'):>8} "
              f"{rate('control'):>8} {int(r.parse_ok.sum()):>3}/{len(r):<3} {lat:>8.1f}")

    Path(args.out_json).write_text(json.dumps(results, indent=2, default=str))
    print(f"\nPer-case results -> {args.out_json}")


if __name__ == "__main__":
    main()
