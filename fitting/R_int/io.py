#!/usr/bin/env python
# coding: utf-8

import logging

import pandas as pd


def load_data(file_path: str) -> pd.DataFrame:
    """Load data from a text file into a Pandas DataFrame.

    Parameters:     file_path (str): Path to the data file.

    Returns:     pd.DataFrame: Loaded DataFrame.
    """
    try:
        df = pd.read_table(file_path)
        logging.info("Data loaded successfully from %s.", file_path)
        logging.debug("DataFrame columns: %s", df.columns.tolist())
        return df
    except Exception:
        logging.exception("Error loading data from %s", file_path)
        raise


def save_processed_data(df: pd.DataFrame, file_path: str) -> None:
    """Save the processed DataFrame to a text file.

    Parameters:     df (pd.DataFrame): Processed DataFrame.     file_path (str): Path to
    save the DataFrame.
    """
    try:
        df.to_csv(file_path, sep="\t", index=True)
        logging.info("Processed data saved to %s.", file_path)
    except Exception:
        logging.exception("Error saving processed data to %s", file_path)
        raise
