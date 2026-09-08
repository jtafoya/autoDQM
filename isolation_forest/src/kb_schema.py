"""Validation helpers for the human-authored AutoDQM knowledge base."""

from __future__ import annotations

from typing import Any, List, Mapping, Tuple


KB_KEYS = ("run", "category", "cause", "action", "recovery")
KB_DIAGNOSTIC_KEYS = KB_KEYS[1:]


def parse_kb_run(value: Any) -> Tuple[int, int]:
    """Parse an integer run or exact ``START-END`` run range."""
    if isinstance(value, bool):
        raise ValueError("KB run must be an integer or an exact START-END string")
    if isinstance(value, int):
        if value < 0:
            raise ValueError("KB run integers must be non-negative")
        return value, value
    if isinstance(value, str):
        parts = value.split("-")
        if len(parts) != 2 or not all(part.isascii() and part.isdigit() for part in parts):
            raise ValueError(f"Invalid KB run range: {value!r}")
        start, end = (int(part) for part in parts)
        if start > end:
            raise ValueError(f"KB run range starts after it ends: {value!r}")
        return start, end
    raise ValueError(f"Invalid KB run value: {value!r}")


def validate_kb_entries(entries: Any) -> List[dict]:
    """Validate the exact five-key schema, key order, run types, and uniqueness."""
    if not isinstance(entries, list):
        raise ValueError("Knowledge base must contain a YAML list")

    validated: List[dict] = []
    seen_runs = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(f"KB entry {index} must be a mapping")
        actual_keys = tuple(entry.keys())
        if actual_keys != KB_KEYS:
            raise ValueError(
                f"KB entry {index} keys must be exactly {KB_KEYS} in that order; "
                f"found {actual_keys}"
            )
        bounds = parse_kb_run(entry["run"])
        if bounds in seen_runs:
            raise ValueError(f"Duplicate KB run/range at entry {index}: {entry['run']!r}")
        seen_runs.add(bounds)
        validated.append(dict(entry))
    return validated


def validate_manual_entries(entries: Any) -> List[dict]:
    """Validate manual entries and require all diagnostic fields to be nonblank."""
    validated = validate_kb_entries(entries)
    for entry in validated:
        blank = [
            key for key in KB_DIAGNOSTIC_KEYS
            if entry[key] is None or not str(entry[key]).strip()
        ]
        if blank:
            raise ValueError(f"Manual KB entry {entry['run']!r} has blank fields: {blank}")
    return validated
