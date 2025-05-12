#!/usr/bin/env python
# coding: utf-8

import logging
from typing import Any, Dict

import lmfit as lf  # type: ignore
import numpy as np
from lmfit.model import ModelResult  # type: ignore


def fit_callback(
    params: Dict[str, Any], iter: int, resid: np.ndarray, *args, **kwargs
) -> bool:
    """
    Callback for fitting iterations to log chi-square value.
    """
    chi_sq = np.sum(resid**2)
    logging.info("Iteration %d: chi-square = %f", iter, chi_sq)
    return False


def perform_fitting(
    model: lf.Model, params: lf.Parameters, I_int: np.ndarray, V_int: np.ndarray
) -> ModelResult:
    """
    Perform the fitting using lmfit.

    Parameters:
        model (lf.Model): The lmfit model.
        params (lf.Parameters): The model parameters.
        I_int (np.ndarray): Current array.
        V_int (np.ndarray): Voltage array.

    Returns:
        ModelResult: The result of the fitting process.
    """
    valid = ~np.isnan(V_int) & ~np.isnan(I_int)
    I_valid = I_int[valid]
    V_valid = V_int[valid]
    result = model.fit(
        V_valid,
        params,
        I_ints=I_valid,
        weights=V_valid**2,
        iter_cb=fit_callback,
        max_nfev=100,
    )
    logging.info("Fitting completed.")
    return result
