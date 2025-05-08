#!/usr/bin/env python
# coding: utf-8

import logging

import pandas as pd


def load_data(file_path: str) -> pd.DataFrame:
    """
    Load data from a text file into a Pandas DataFrame.

    Parameters:
        file_path (str): Path to the data file.

    Returns:
        pd.DataFrame: Loaded DataFrame.
    """
    try:
        df = pd.read_table(file_path)
        logging.info(f"Data loaded successfully from {file_path}.")
        logging.debug(f"DataFrame columns: {df.columns.tolist()}")
        return df
    except Exception:
        logging.exception(f"Error loading data from {file_path}")
        raise


def save_processed_data(df: pd.DataFrame, file_path: str):
    """
    Save the processed DataFrame to a text file.

    Parameters:
        df (pd.DataFrame): Processed DataFrame.
        file_path (str): Path to save the DataFrame.
    """
    try:
        df.to_csv(file_path, sep="\t", index=True)
        logging.info(f"Processed data saved to {file_path}.")
    except Exception:
        logging.exception(f"Error saving processed data to {file_path}")
        raise
