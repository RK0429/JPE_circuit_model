#!/usr/bin/env python
# coding: utf-8

import logging

import lmfit as lf  # type: ignore
import numpy as np
from lmfit.model import ModelResult  # type: ignore


def setup_fitting_model(output_power_fn) -> lf.Model:
    """
    Set up the RLC series model for output power fitting.

    Returns:
        lf.Model: The lmfit Model for output_power.
    """
    return lf.Model(output_power_fn, independent_vars=["V", "R_int"])


def perform_fitting(
    model: lf.Model,
    params: lf.Parameters,
    V: np.ndarray,
    R_int: np.ndarray,
    data: np.ndarray,
    weights: np.ndarray,
) -> ModelResult:
    """
    Perform the fitting using the provided model, parameters, and data.

    Parameters:
        model (lf.Model): The lmfit model.
        params (lf.Parameters): The model parameters.
        V (np.ndarray): Voltage array.
        R_int (np.ndarray): Internal resistance array.
        data (np.ndarray): Dependent variable data to fit.
        weights (np.ndarray): Weights for the fitting.

    Returns:
        ModelResult: The result of the fitting process.
    """
    result = model.fit(data, params, V=V, R_int=R_int, weights=weights)
    logging.info("Fitting completed.")
    logging.info(result.fit_report())
    logging.info(f"Best fit values: {result.best_values}")
    return result
