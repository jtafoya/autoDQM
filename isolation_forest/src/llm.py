"""
LLM-based anomaly categorization for confirmed [ALERT] events.

Called by monitor.py when llm_enabled=True in config. On each [ALERT], loads
data/llm_knowledge_base.yaml (human-maintained resolved examples, not an
exhaustive failure taxonomy) and auto-injects the anomaly snapshot
for each referenced run by reading it from the existing anomaly log CSV.  The
assembled prompt is sent to the configured LLM; the response is appended to a
JSON sidecar file co-located with the anomaly log.

Provider abstraction
--------------------
All provider-specific code lives in _call_api().  To add a new provider:
  1. Add an elif branch in _call_api() that accepts (system, user, model) → str.
  2. Install the provider's Python package and add it to requirements.txt.
  3. Set llm_provider in config.yaml to the new provider name.
Everything else (prompt assembly, KB loading, output parsing, sidecar writing)
is provider-agnostic and requires no changes.

Currently supported providers:  anthropic, openai

Requires the provider-specific API key in the environment:
  anthropic -> ANTHROPIC_API_KEY
  openai    -> OPENAI_API_KEY
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import yaml


# ── Provider dispatch ─────────────────────────────────────────────────────────

def _call_api(system: str, user: str, model: str, provider: str) -> str:
    """
    Send a prompt to the configured LLM and return the raw text response.

    Parameters
    ----------
    system   : system prompt string.
    user     : user prompt string.
    model    : model identifier passed to the provider API.
    provider : provider name (e.g. "anthropic" or "openai").

    To add a new provider, add an elif branch here, install its package,
    and update requirements.txt accordingly.
    """
    if provider == "anthropic":
        import anthropic  # not imported at module level — optional dependency
        client  = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text.strip()

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI()
        response = client.responses.create(
            model=model,
            instructions=system,
            input=user,
        )
        return response.output_text.strip()

    raise NotImplementedError(
        f"LLM provider '{provider}' is not implemented.  "
        "Add an elif branch in src/llm.py:_call_api() to support it."
    )


# ── Prompt constants ──────────────────────────────────────────────────────────

_SYSTEM = (
    "You diagnose detector anomalies using current alert evidence and a non-exhaustive "
    "set of resolved historical cases. Historical cases are evidence and analogical "
    "references, not a complete taxonomy of possible failures. If no exact match exists, "
    "state that explicitly, identify any partial similarities, and still propose cautious, "
    "evidence-grounded diagnostic hypotheses. Separate OBSERVED facts supplied in the "
    "current alert from INFERRED interpretations and UNKNOWN information needed to test "
    "them. Never present an unprovided measurement as an observation, and never convert a "
    "recommended diagnostic check into an alleged fact. For each hypothesis, identify "
    "supporting and contradicting evidence, missing information, discriminating checks, "
    "and a possible corrective action that is clearly conditional on the diagnosis. Do not "
    "force a target into a category merely because that category appears in the historical "
    "knowledge. Confidence must reflect evidence quality and use only low, medium, or high."
)

_TASK = """
---
## Task

First classify the relationship to historical knowledge:
- exact: close reproduction of a historical incident with no important contradiction
- partial: meaningful similarity with important differences or missing evidence
- unseen: no historical case closely explains the observed pattern

An unseen relationship does not end the diagnosis. Rank up to three plausible causes using
the supplied detector evidence, historical analogy where useful, and cautious detector/DAQ
reasoning. Categories are free text and need not occur in the historical cases. Use historical
case IDs exactly as supplied; matched_cases may be empty. Return ONLY valid JSON:

{
  "target_id": "identifier from the current alert",
  "known_case_match": "exact | partial | unseen",
  "observed_evidence": ["fact directly supplied in the target alert"],
  "candidates": [
    {
      "rank": 1,
      "category": "free-text diagnostic category",
      "likely_cause": "diagnostic hypothesis",
      "hypothesis_basis": "historical_match | analogy | novel_inference",
      "confidence": "low | medium | high",
      "matched_cases": ["historical case IDs, or empty"],
      "supporting_similarities": ["supplied evidence supporting the hypothesis"],
      "contradicting_evidence": ["supplied evidence inconsistent with it"],
      "recommended_diagnostic_checks": ["measurement or inspection that tests it"],
      "possible_fix": "conditional corrective action"
    }
  ],
  "missing_information": ["information needed for a stronger diagnosis"],
  "reasoning": "concise synthesis"
}
"""


# ── Snapshot helpers ──────────────────────────────────────────────────────────

def _summarise_anomaly_df(df: pd.DataFrame, top_n: int = 5) -> str:
    """Render detector evidence without dropping IF-only or missing-channel rows."""
    if df.empty:
        return "  (no anomaly data)"

    rows = df.copy()
    for column in ("method", "max_z", "if_score", "triggered_features"):
        if column not in rows.columns:
            rows[column] = pd.NA

    method_text = rows["method"].fillna("").astype(str)
    if_only = method_text.eq("isolation_forest")
    finite_z = pd.to_numeric(rows["max_z"], errors="coerce").notna()

    # Statistical anomalies use largest max_z first.  Isolation-forest scores
    # use the detector's convention: smaller/more-negative is more anomalous.
    z_ranked = rows[finite_z & ~if_only].sort_values("max_z", ascending=False)
    if_ranked = rows[if_only].sort_values("if_score", ascending=True, na_position="last")
    other_ranked = rows[~finite_z & ~if_only]
    top = pd.concat([
        z_ranked.head(top_n),
        if_ranked.head(top_n),
        other_ranked.head(top_n),
    ])

    def number(value: object, precision: int) -> str:
        return "n/a" if pd.isna(value) else f"{float(value):.{precision}f}"

    lines = []
    for ch, row in top.iterrows():
        method = row.get("method")
        method = "n/a" if pd.isna(method) or str(method).strip() == "" else str(method)
        features = row.get("triggered_features")
        features = "none" if pd.isna(features) or str(features).strip() == "" else str(features)
        lines.append(
            f"  channel={ch}  method={method}  max_z={number(row.get('max_z'), 1)}"
            f"  if_score={number(row.get('if_score'), 3)}  features=[{features}]"
        )
    if len(rows) > len(top):
        lines.append(f"  ... and {len(rows) - len(top)} more anomalous channels")
    return "\n".join(lines)


def _historical_snapshot(log_path: str, run: int) -> str:
    """
    Pull the anomaly snapshot for a historical run from the log CSV.

    Returns a human-readable string.  Returns a graceful message if the run is
    absent from the log or the log cannot be read — does not raise.
    """
    try:
        df = pd.read_csv(log_path)
        if df.empty:
            return "  (log is empty)"
        from .run_list import parse_run_subrun
        parsed = df["filename"].apply(
            lambda f: pd.Series(parse_run_subrun(f), index=["run", "subrun"])
        )
        df = pd.concat([df, parsed], axis=1).dropna(subset=["run"])
        df["run"]    = df["run"].astype(int)
        df["subrun"] = df["subrun"].astype(int)

        run_df = df[df["run"] == run]
        if run_df.empty:
            return f"  (run {run} not found in log — annotation used without snapshot)"

        anomalous     = run_df[run_df["anomalous"] == True]
        n_subruns     = run_df["subrun"].nunique()
        n_bad_subruns = anomalous["subrun"].nunique() if not anomalous.empty else 0
        snapshot_df   = anomalous.set_index("channel") if not anomalous.empty else anomalous

        lines = [
            f"  Subruns in log: {n_subruns}  |  subruns with anomalies: {n_bad_subruns}",
            f"  Total anomalous channel-entries: {len(anomalous)}",
            "  Detector-ranked anomalous channels:",
            _summarise_anomaly_df(snapshot_df),
        ]
        return "\n".join(lines)

    except Exception as exc:
        return f"  (error loading snapshot for run {run}: {exc})"


# ── Prompt assembly ───────────────────────────────────────────────────────────

def _format_current_alert(
    run: int,
    subrun: int,
    alert_reasons: list[str],
    anomalous_df: pd.DataFrame,
) -> str:
    return (
        f"Target ID: run_{run}_subrun_{subrun}\n"
        f"Run {run}, subrun {subrun} — ALERT\n"
        f"Conditions: {', '.join(alert_reasons)}\n"
        f"Anomalous channels ({len(anomalous_df)} total, detector-ranked evidence):\n"
        + _summarise_anomaly_df(anomalous_df)
    )


def _format_historical_case(entry: dict, snapshot: str) -> str:
    return (
        f"### Historical case ID: case_run_{entry['run']}\n"
        f"Source run: {entry['run']}\n"
        f"Anomaly data (auto-injected from log):\n{snapshot}\n"
        f"Human annotation:\n"
        f"  Category : {entry.get('category', 'unknown')}\n"
        f"  Cause    : {entry.get('cause', 'unspecified')}\n"
        f"  Action   : {entry.get('action', 'unspecified')}\n"
        f"  Recovery : {entry.get('recovery', 'unspecified')}"
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def query_llm(
    run: int,
    subrun: int,
    alert_reasons: list[str],
    anomalous_df: pd.DataFrame,
    knowledge_base_path: str,
    historical_log_path: str,
    suggestions_path: str,
    model: str,
    provider: str,
) -> dict:
    """
    Categorize a confirmed [ALERT] using the configured LLM provider.

    Parameters
    ----------
    run, subrun          : identifiers of the alerted file.
    alert_reasons        : list of human-readable alert condition strings built
                           by process_file() (e.g. ["2 persistent anomalous ch"]).
    anomalous_df         : DataFrame of anomalous channels, index=channel id,
                           columns include max_z, if_score, triggered_features.
    knowledge_base_path  : path to data/llm_knowledge_base.yaml.
    historical_log_path  : path to the anomaly log CSV used to fetch historical
                           run snapshots (usually the live log or a batch log).
    suggestions_path     : path to the JSON sidecar to append the result to.
    model                : model ID passed to the provider API.
    provider             : provider name; must match a branch in _call_api().

    Returns the parsed suggestion dict. Responses separate observed
    evidence, exact/partial/unseen match status, ranked hypotheses, missing
    information, checks, and conditional fixes. On failure, an error dict is
    still appended to suggestions_path so failures remain visible.
    """
    kb_path = Path(knowledge_base_path)
    if not kb_path.exists():
        result = {"error": f"knowledge base not found: {knowledge_base_path}"}
        result.update({"run": run, "subrun": subrun})
        _append_suggestion(suggestions_path, result)
        return result

    knowledge_base: list[dict] = yaml.safe_load(kb_path.read_text()) or []
    if not knowledge_base:
        result = {"error": "knowledge base is empty", "run": run, "subrun": subrun}
        _append_suggestion(suggestions_path, result)
        return result

    current_block = _format_current_alert(run, subrun, alert_reasons, anomalous_df)
    case_blocks = [
        _format_historical_case(
            entry,
            _historical_snapshot(historical_log_path, entry["run"]),
        )
        for entry in knowledge_base
    ]

    user_prompt = (
        "## Current alert\n\n"
        + current_block
        + "\n\n---\n\n## Historical reference cases\n\n"
        + "\n\n".join(case_blocks)
        + _TASK
    )

    try:
        raw        = _call_api(_SYSTEM, user_prompt, model, provider)
        suggestion = json.loads(raw)
    except json.JSONDecodeError:
        suggestion = {"raw_response": raw, "parse_error": "LLM returned non-JSON"}
    except Exception as exc:
        print(f"[LLM ERROR] {exc}", file=sys.stderr)
        suggestion = {"api_error": str(exc)}

    suggestion["run"]    = run
    suggestion["subrun"] = subrun
    _append_suggestion(suggestions_path, suggestion)
    return suggestion


def _append_suggestion(path: str, entry: dict) -> None:
    """Append one entry to the JSON sidecar, creating it if absent."""
    p = Path(path)
    existing: list = []
    if p.exists() and p.stat().st_size > 0:
        try:
            existing = json.loads(p.read_text())
        except json.JSONDecodeError:
            existing = []  # truncated or corrupt sidecar — start fresh
    existing.append(entry)
    p.write_text(json.dumps(existing, indent=2))
