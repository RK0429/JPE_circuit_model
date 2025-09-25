"""Utilities for fitting the internal resistance model with lmfit."""

from __future__ import annotations

import logging
from typing import Any

import lmfit as lf
import numpy as np
from lmfit.model import ModelResult
from numpy.typing import NDArray

CURRENT_LOGGER = logging.getLogger(__name__)

FloatArray = NDArray[np.float64]


def fit_callback(
    params: dict[str, Any],
    iteration: int,
    residuals: FloatArray,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Log the chi-square value at each fitting iteration."""
    _ = (params, args, kwargs)
    chi_sq = float(np.sum(residuals**2))
    CURRENT_LOGGER.info("Iteration %d: chi-square = %.6f", iteration, chi_sq)
    return False


def perform_fitting(
    model: lf.Model,
    params: lf.Parameters,
    current_internal: FloatArray,
    voltage_internal: FloatArray,
) -> ModelResult:
    """Fit the lmfit ``model`` to the provided current/voltage data."""
    valid_mask = ~np.isnan(voltage_internal) & ~np.isnan(current_internal)
    valid_currents = current_internal[valid_mask]
    valid_voltages = voltage_internal[valid_mask]

    result = model.fit(
        valid_voltages,
        params,
        currents=valid_currents,
        weights=valid_voltages**2,
        iter_cb=fit_callback,
        max_nfev=100,
    )
    CURRENT_LOGGER.info("Fitting completed")
    return result
