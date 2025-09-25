"""Helper utilities to configure and run lmfit-based antenna parameter fitting."""

from __future__ import annotations

import logging
from collections.abc import Callable

import lmfit as lf
import numpy as np
from lmfit.model import ModelResult
from numpy.typing import NDArray

LOGGER = logging.getLogger(__name__)

FloatArray = NDArray[np.float64]


def setup_fitting_model(output_power_fn: Callable[..., FloatArray]) -> lf.Model:
    """Build an ``lmfit`` model that wraps ``output_power_fn``."""
    return lf.Model(
        output_power_fn,
        independent_vars=["voltage", "internal_resistance"],
    )


def perform_fitting(
    model: lf.Model,
    params: lf.Parameters,
    voltage: FloatArray,
    internal_resistance: FloatArray,
    measured_power: FloatArray,
    weights: FloatArray,
) -> ModelResult:
    """Fit ``model`` to the experimental ``measured_power``."""
    result = model.fit(
        measured_power,
        params,
        voltage=voltage,
        internal_resistance=internal_resistance,
        weights=weights,
    )
    LOGGER.info("Fitting completed")
    LOGGER.info("Best fit values: %s", result.best_values)
    return result
