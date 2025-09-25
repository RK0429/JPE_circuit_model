"""I/O helpers for antenna parameter fitting workflows."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

LOGGER = logging.getLogger(__name__)


def load_data(
    bolometer_path: str,
    ive_path: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the bolometer output and IV characteristic tables."""
    bolometer_df = pd.read_csv(Path(bolometer_path), sep="\t")
    ive_df = pd.read_csv(Path(ive_path), sep="\t")
    LOGGER.info("Experimental data loaded successfully")
    return bolometer_df, ive_df


def load_txt_data(filename: str) -> pd.DataFrame:
    """Read a whitespace-delimited text file into a dataframe."""
    dataframe = pd.read_csv(Path(filename), delim_whitespace=True)
    LOGGER.info("Text data loaded successfully from %s", filename)
    return dataframe
