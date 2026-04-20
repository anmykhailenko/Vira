"""Lightweight validation helpers for raw dataset auditing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.load_data import EXPECTED_COLUMNS, load_all_datasets, resolve_data_file
from src.utils.config import RAW_DATA_DIR


def _schema_summary(df: pd.DataFrame) -> dict[str, str]:
    """Return a simple column-to-dtype mapping."""
    return {column: str(dtype) for column, dtype in df.dtypes.items()}


def _missing_summary(df: pd.DataFrame) -> dict[str, int]:
    """Return missing values per column."""
    return {column: int(count) for column, count in df.isna().sum().items()}


def _duplicate_summary(name: str, df: pd.DataFrame) -> dict[str, int]:
    """Return dataset-specific duplicate checks."""
    summary = {"duplicate_rows": int(df.duplicated().sum())}

    if name == "users":
        summary["duplicate_user_id"] = int(df.duplicated(subset=["user_id"]).sum())
        summary["duplicate_user_game_pair"] = int(df.duplicated(subset=["user_id", "game_id"]).sum())
    elif name == "sessions":
        summary["duplicate_session_id"] = int(df.duplicated(subset=["session_id"]).sum())
        summary["duplicate_user_session_start"] = int(df.duplicated(subset=["user_id", "session_start"]).sum())
    elif name == "transactions":
        summary["duplicate_transaction_signature"] = int(
            df.duplicated(subset=["user_id", "transaction_date", "product_type", "revenue_usd", "is_trial"]).sum()
        )
    elif name == "events":
        summary["duplicate_event_signature"] = int(
            df.duplicated(subset=["user_id", "event_timestamp", "event_name", "event_params"]).sum()
        )

    return summary


def _date_summary(name: str, df: pd.DataFrame) -> dict[str, dict[str, str]]:
    """Return min and max values for known parsed date columns."""
    summary: dict[str, dict[str, str]] = {}
    for column in EXPECTED_COLUMNS[name]:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            summary[column] = {"min": str(df[column].min()), "max": str(df[column].max())}
    return summary


def _integrity_checks(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Return cross-table integrity checks and obvious data risks."""
    users = datasets["users"]
    sessions = datasets["sessions"]
    transactions = datasets["transactions"]
    events = datasets["events"]

    known_user_ids = set(users["user_id"].dropna().astype(str))
    session_duration_seconds = (sessions["session_end"] - sessions["session_start"]).dt.total_seconds()

    return {
        "missing_foreign_keys": {
            "sessions_user_id": int((~sessions["user_id"].isin(known_user_ids)).sum()),
            "transactions_user_id": int((~transactions["user_id"].isin(known_user_ids)).sum()),
            "events_user_id": int((~events["user_id"].isin(known_user_ids)).sum()),
        },
        "users_not_globally_unique": int(users["user_id"].duplicated().sum()),
        "negative_session_durations": int((session_duration_seconds < 0).fillna(False).sum()),
        "zero_revenue_transactions": int((transactions["revenue_usd"] == 0).sum()),
    }


def _event_params_notes(events: pd.DataFrame, sample_size: int = 10000) -> dict[str, Any]:
    """Inspect event_params as JSON-like strings without expanding them."""
    parsed_ok = 0
    sampled_keys: dict[str, set[str]] = {}

    sample = events.sample(n=min(sample_size, len(events)), random_state=42)
    for _, row in sample.iterrows():
        try:
            parsed = json.loads(row["event_params"])
        except (TypeError, json.JSONDecodeError):
            continue

        parsed_ok += 1
        if isinstance(parsed, dict):
            sampled_keys.setdefault(str(row["event_name"]), set()).update(parsed.keys())

    return {
        "sample_size": min(sample_size, len(events)),
        "json_parse_successes": parsed_ok,
        "sampled_param_keys_by_event": {
            event_name: sorted(keys) for event_name, keys in sorted(sampled_keys.items())
        },
    }


def audit_raw_data(raw_data_dir: Path = RAW_DATA_DIR) -> dict[str, Any]:
    """Run a lightweight reusable audit over all raw datasets."""
    datasets = load_all_datasets(raw_data_dir=raw_data_dir)
    audit: dict[str, Any] = {"files": {}, "integrity": {}, "event_params": {}}

    for name, df in datasets.items():
        file_path = resolve_data_file(name, raw_data_dir=raw_data_dir)
        audit["files"][name] = {
            "file_name": file_path.name,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "schema": _schema_summary(df),
            "missing_values": _missing_summary(df),
            "duplicates": _duplicate_summary(name, df),
            "date_summary": _date_summary(name, df),
        }

    audit["integrity"] = _integrity_checks(datasets)
    audit["event_params"] = _event_params_notes(datasets["events"])
    return audit
