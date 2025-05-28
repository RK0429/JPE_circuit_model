#!/usr/bin/env python
# coding: utf-8

import logging

import pandas as pd


def process_data(df: pd.DataFrame) -> pd.DataFrame:
    """Process the DataFrame by calculating power and resistance.

    Parameters:     df (pd.DataFrame): Original DataFrame.

    Returns:     pd.DataFrame: Processed DataFrame with 'Power' and 'Resistance'
    columns.
    """
    df_processed = df.copy()

    if "Reduced Voltage" in df_processed.columns and "Current" in df_processed.columns:
        df_processed["Power"] = (
            df_processed["Reduced Voltage"] * df_processed["Current"] * 1e-3
        )
        df_processed["Resistance"] = (
            df_processed["Reduced Voltage"] / df_processed["Current"] * 1e3
        )
        logging.info("Calculated 'Power' and 'Resistance' columns.")
    else:
        missing = {"Reduced Voltage", "Current"} - set(df_processed.columns)
        logging.error(f"Missing columns for processing: {missing}")
        raise KeyError(f"Missing columns: {missing}")

    return df_processed
