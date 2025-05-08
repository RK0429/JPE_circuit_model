#!/usr/bin/env python
# coding: utf-8

import logging
from typing import Tuple

import pandas as pd


def load_data(
    bo_file_path: str,
    ive_file_path: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load experimental data from specified file paths.

    Parameters:
        bo_file_path (str): Path to the Bolometer Output data file.
        ive_file_path (str): Path to the IVE data file.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: DataFrames containing Bolometer Output and IVE data.
    """
    try:
        bolometer_df = pd.read_table(bo_file_path)
        ive_df = pd.read_table(ive_file_path)
        logging.info("Experimental data loaded successfully.")
        return bolometer_df, ive_df
    except Exception as e:
        logging.error(f"Error loading experimental data: {e}")
        raise


def load_txt_data(filename: str) -> pd.DataFrame:
    """
    Load data from a text file with whitespace delimiter.

    Parameters:
        filename (str): Path to the text file.

    Returns:
        pd.DataFrame: DataFrame containing the loaded data.
    """
    try:
        df = pd.read_csv(filename, delim_whitespace=True)
        logging.info(f"Text data loaded successfully from {filename}.")
        return df
    except Exception as e:
        logging.error(f"Error loading text data: {e}")
        raise
