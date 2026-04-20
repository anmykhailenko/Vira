"""Shared project paths and small runtime defaults."""

from pathlib import Path


# Resolve from this file so imports work from notebooks and from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "ds_test_task_dataset"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORTS_DIR = PROJECT_ROOT / "reports"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

DEFAULT_RANDOM_SEED = 42


def ensure_output_dirs() -> list[Path]:
    """Create key writable project directories when they are missing."""
    directories = [PROCESSED_DATA_DIR, OUTPUTS_DIR, FIGURES_DIR, REPORTS_DIR]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    return directories
