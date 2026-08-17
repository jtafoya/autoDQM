"""
LLM-based anomaly categorization for confirmed [ALERT] events.

Called by monitor.py when llm_enabled=True in config. On each [ALERT], loads
data/llm_knowledge_base.yaml (human-maintained: one entry per known bad run,
with category, cause, action, recovery) and auto-injects the anomaly snapshot
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

Currently supported providers:  anthropic

Requires: ANTHROPIC_API_KEY set in the environment (anthropic provider).
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
    provider : provider name (e.g. "anthropic").

    To add a new provider, add an elif branch here, install its package,
    and update requirements.txt accordingly.
    """
    if provider == "anthropic":
        import anthropic  # not imported at module level — optional dependency
        client  = anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            # max_tokens caps thinking + answer together on Claude 5-era models
            # (thinking is on by default there), so leave headroom beyond the
            # ~300-token JSON answer or the response truncates mid-thought.
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Claude 5-era models prepend a thinking block to content; the answer
        # is the first text-type block, never content[0] unconditionally.
        for block in message.content:
            if block.type == "text":
                return block.text.strip()
        return ""

    raise NotImplementedError(
        f"LLM provider '{provider}' is not implemented.  "
        "Add an elif branch in src/llm.py:_call_api() to support it."
    )


# ── Prompt constants ──────────────────────────────────────────────────────────

_SYSTEM = (
    "You are a DQM expert for the MilliQan bar/slab detector. "
    "You receive anomaly reports from an automated isolation forest pipeline "
    "and must categorize them based on historical known failure patterns. "
    "Be concise and specific. If no historical case is a good match, say so."
)

_TASK = """
---
## Task

Match the current alert to historical cases.  Include every candidate that is
meaningfully supported by the evidence — one entry if only one pattern fits,
several if the cause is ambiguous.  Rank them best-match first.
Return ONLY valid JSON with no surrounding text:

{
  "candidates": [
    {
      "rank":             1,
      "category":         "short snake_case label",
      "likely_cause":     "one sentence",
      "suggested_action": "specific, actionable next step",
      "matched_runs":     [run numbers from historical cases that support this candidate, or []],
      "confidence":       "high | medium | low"
    }
  ],
  "reasoning": "one sentence explaining the top match and any ambiguity"
}
"""


# ── Snapshot helpers ──────────────────────────────────────────────────────────

def _summarise_anomaly_df(df: pd.DataFrame, top_n: int = 5) -> str:
    """Render the top-N rows of an anomalous-channel DataFrame as readable text."""
    valid = df.dropna(subset=["max_z"]) if "max_z" in df.columns else df
    if valid.empty:
        return "  (no anomaly data)"
    top = valid.nlargest(top_n, "max_z")
    lines = []
    for ch, row in top.iterrows():
        lines.append(
            f"  ch{ch}: max_z={row['max_z']:.1f}  if_score={row['if_score']:.3f}"
            f"  features=[{row.get('triggered_features', '')}]"
        )
    if len(valid) > top_n:
        lines.append(f"  ... and {len(valid) - top_n} more anomalous channels")
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
            "  Top channels (by max_z):",
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
        f"Run {run}, subrun {subrun} — ALERT\n"
        f"Conditions: {', '.join(alert_reasons)}\n"
        f"Anomalous channels ({len(anomalous_df)} total, top by max_z):\n"
        + _summarise_anomaly_df(anomalous_df)
    )


def _format_historical_case(entry: dict, snapshot: str) -> str:
    return (
        f"### Case: run {entry['run']}\n"
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

    Returns the parsed suggestion dict with a "candidates" list (ranked best-match
    first, each with category, likely_cause, suggested_action, matched_runs,
    confidence) and a top-level "reasoning" string.  On any failure, returns an
    error dict and still appends it to suggestions_path so failures are visible.
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
