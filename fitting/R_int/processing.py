"""Data wrangling helpers for the internal resistance fitting workflow."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import pandas as pd

LOGGER = logging.getLogger(__name__)

_REQUIRED_COLUMNS: tuple[str, str] = ("Reduced Voltage", "Current")


def _validate_columns(columns: Sequence[str]) -> None:
    missing = set(_REQUIRED_COLUMNS) - set(columns)
    if missing:
        LOGGER.error("Missing columns for processing: %s", sorted(missing))
        raise KeyError(tuple(sorted(missing)))


def process_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Calculate derived power and resistance columns."""
    _validate_columns(dataframe.columns)
    processed = dataframe.copy()

    voltage = processed["Reduced Voltage"]
    current_milliamp = processed["Current"]

    processed["Power"] = voltage * current_milliamp * 1e-3
    processed["Resistance"] = voltage / current_milliamp * 1e3

    LOGGER.info("Calculated columns 'Power' and 'Resistance'")
    return processed
