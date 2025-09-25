"""I/O helpers for the internal resistance fitting workflow."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


def load_data(file_path: str) -> pd.DataFrame:
    """Read the raw measurement table stored in ``file_path``."""
    path = Path(file_path)
    dataframe = pd.read_csv(path, sep="\t")
    LOGGER.info("Data loaded successfully from %s", path)
    LOGGER.debug("Columns: %s", list(dataframe.columns))
    return dataframe


def save_processed_data(dataframe: pd.DataFrame, file_path: str) -> None:
    """Persist the processed dataset to ``file_path`` using tab-separated values."""
    path = Path(file_path)
    dataframe.to_csv(path, sep="\t", index=True)
    LOGGER.info("Processed data saved to %s", path)
