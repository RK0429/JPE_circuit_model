#!/usr/bin/env python
# coding: utf-8

from typing import Any, Union

import numpy as np
from numpy.typing import NDArray


def T2R_int(
    T: Union[float, NDArray[Any]], A: float, B: float, C: float, D: float
) -> Union[float, NDArray[Any]]:
    """Calculate thermal resistance from temperature."""
    return A * (np.exp(-T / B) + np.exp(-(T**2) / C)) + D


def P2T(
    P: Union[float, NDArray[Any]], R_th: float, T_bath: float
) -> Union[float, NDArray[Any]]:
    """Calculate temperature from power."""
    return R_th * P + T_bath


def T2R_th(
    T: Union[float, NDArray[Any]], alpha: float, beta: float, gamma: float
) -> Union[float, NDArray[Any]]:
    """Calculate thermal resistance from temperature (alternative model)."""
    return gamma / (1 - alpha * np.exp(-beta * T))
