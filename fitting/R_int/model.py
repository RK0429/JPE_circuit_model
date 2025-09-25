"""Analytical expressions used in the internal resistance fitting model."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]


def internal_resistance_from_temperature(
    temperature: float | FloatArray,
    coeff_a: float,
    coeff_b: float,
    coeff_c: float,
    coeff_d: float,
) -> float | FloatArray:
    """Return the internal resistance for a given ``temperature``."""
    exp_term = np.exp(-temperature / coeff_b) + np.exp(-(temperature**2) / coeff_c)
    return coeff_a * exp_term + coeff_d


def temperature_from_power(
    power: float | FloatArray,
    thermal_resistance: float,
    bath_temperature: float,
) -> float | FloatArray:
    """Convert dissipated ``power`` into device temperature."""
    return thermal_resistance * power + bath_temperature


def thermal_resistance_from_temperature(
    temperature: float | FloatArray,
    alpha: float,
    beta: float,
    gamma: float,
) -> float | FloatArray:
    """Return the thermal resistance predicted by the alternative model."""
    return gamma / (1 - alpha * np.exp(-beta * temperature))
