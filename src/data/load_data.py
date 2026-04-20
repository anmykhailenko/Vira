"""Reusable raw-data loaders for the Vira Games segmentation project."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.config import RAW_DATA_DIR

DATASET_FILE_STEMS = {
    "users": "users",
    "sessions": "sessions",
    "transactions": "transactions",
    "events": "events",
}

EXPECTED_COLUMNS = {
    "users": ["user_id", "install_date", "install_source", "country", "device_os", "game_id"],
    "sessions": [
        "user_id",
        "session_id",
        "session_start",
        "session_end",
        "levels_completed",
        "levels_failed",
    ],
    "transactions": ["user_id", "transaction_date", "product_type", "revenue_usd", "is_trial"],
    "events": ["user_id", "event_timestamp", "event_name", "event_params"],
}

STRING_DTYPES = {
    "users": {
        "user_id": "string",
        "install_source": "string",
        "country": "string",
        "device_os": "string",
        "game_id": "string",
    },
    "sessions": {
        "user_id": "string",
        "session_id": "string",
        "levels_completed": "Int64",
        "levels_failed": "Int64",
    },
    "transactions": {
        "user_id": "string",
        "product_type": "string",
        "revenue_usd": "float64",
        "is_trial": "boolean",
    },
    "events": {
        "user_id": "string",
        "event_name": "string",
        "event_params": "string",
    },
}

DATE_COLUMNS = {
    "users": ["install_date"],
    "sessions": ["session_start", "session_end"],
    "transactions": ["transaction_date"],
    "events": ["event_timestamp"],
}


def resolve_data_file(dataset_name: str, raw_data_dir: Path = RAW_DATA_DIR) -> Path:
    """Resolve a raw dataset file by canonical name, tolerating minor extension differences."""
    if dataset_name not in DATASET_FILE_STEMS:
        valid_names = ", ".join(sorted(DATASET_FILE_STEMS))
        raise ValueError(f"Unknown dataset '{dataset_name}'. Expected one of: {valid_names}.")

    stem = DATASET_FILE_STEMS[dataset_name]
    candidates = sorted(
        path
        for path in raw_data_dir.glob(f"{stem}*")
        if path.is_file() and path.suffix.lower() in {".csv", ".gz", ".zip"}
    )

    if not candidates:
        raise FileNotFoundError(f"Could not find a raw file for dataset '{dataset_name}' in {raw_data_dir}.")

    for candidate in candidates:
        name = candidate.name.lower()
        if name in {f"{stem}.csv", f"{stem}.csv.gz", f"{stem}.csv.zip"}:
            return candidate

    return candidates[0]


def _parse_date_columns(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    """Parse known date columns with explicit column-level handling."""
    for column in DATE_COLUMNS[dataset_name]:
        if dataset_name == "users":
            df[column] = pd.to_datetime(df[column], format="%Y-%m-%d", errors="raise")
        else:
            df[column] = pd.to_datetime(df[column], errors="raise", utc=True)
    return df


def load_dataset(dataset_name: str, raw_data_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """Load one canonical raw dataset with explicit schema and date parsing."""
    file_path = resolve_data_file(dataset_name=dataset_name, raw_data_dir=raw_data_dir)
    df = pd.read_csv(file_path, dtype=STRING_DTYPES[dataset_name])
    df = _parse_date_columns(df=df, dataset_name=dataset_name)

    expected_columns = EXPECTED_COLUMNS[dataset_name]
    if list(df.columns) != expected_columns:
        raise ValueError(
            f"Unexpected columns for '{dataset_name}'. "
            f"Expected {expected_columns}, found {list(df.columns)}."
        )

    return df


def load_users(raw_data_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """Load the raw users table."""
    return load_dataset("users", raw_data_dir=raw_data_dir)


def load_sessions(raw_data_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """Load the raw sessions table."""
    return load_dataset("sessions", raw_data_dir=raw_data_dir)


def load_transactions(raw_data_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """Load the raw transactions table."""
    return load_dataset("transactions", raw_data_dir=raw_data_dir)


def load_events(raw_data_dir: Path = RAW_DATA_DIR) -> pd.DataFrame:
    """Load the raw events table."""
    return load_dataset("events", raw_data_dir=raw_data_dir)


def load_all_datasets(raw_data_dir: Path = RAW_DATA_DIR) -> dict[str, pd.DataFrame]:
    """Load all raw datasets with the shared canonical loaders."""
    return {name: load_dataset(name, raw_data_dir=raw_data_dir) for name in DATASET_FILE_STEMS}
