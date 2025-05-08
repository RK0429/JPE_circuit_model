#!/usr/bin/env python
# coding: utf-8

from typing import Tuple

import numpy as np


class Constants:
    """Physical constants used in the analysis."""

    h: float = 6.62607015e-34  # Planck constant (J s)
    hbar: float = h / (2 * np.pi)  # Reduced Planck constant
    mu0: float = 1.25663706212e-6  # Vacuum permeability (H/m)
    ep0: float = 8.8541878128e-12  # Vacuum permittivity (F/m)
    e: float = 1.60217663e-19  # Elementary charge (C)
    Sb: float = 1.75e5  # Specific constant used for scaling


constants = Constants()

# Global parameters for voltage ratio and scaling
N_BOTTOM_MIDDLE: int = 808
VOLTAGE_RATIO: float = (43 + 159) / (15 + 43 + 159)
GAMMA: float = 2 * constants.e / constants.hbar / N_BOTTOM_MIDDLE


def series_sum(*impedances: complex | np.ndarray) -> complex | np.ndarray:
    """
    Calculate the sum of impedances in series, supporting complex scalars and arrays.
    """
    # Initialize result with zero (scalar or array depending on first impedance)
    if not impedances:
        return np.array([], dtype=complex)
    result = impedances[0]
    for z in impedances[1:]:
        result = result + z
    return result


def parallel_sum(*impedances: complex | np.ndarray) -> np.ndarray:
    """
    Calculate the total impedance of parallel impedances.

    Parameters:
        *impedances (complex or np.ndarray): Impedances in parallel.

    Returns:
        np.ndarray: Total parallel impedance.
    """
    susceptances = [1 / z for z in impedances]
    total_susceptance = sum(susceptances)

    # Handle division by zero with small epsilon
    epsilon = 1e-20
    safe_susceptance = np.where(total_susceptance != 0, total_susceptance, epsilon)
    Z_tot = 1.0 / safe_susceptance
    Z_tot = np.where(total_susceptance != 0, Z_tot, np.inf)

    return Z_tot


def mesa_impedance(
    V: np.ndarray,
    R_int: np.ndarray,
    R: float,
    L: float,
    C: float,
    C_intt: float,
    C_intb: float,
    R_loss_t: float,
    R_loss_b: float,
    R_ext: float,
    L_ext: float,
    R_gnd: float,
    R_mid: float,
    R_FG: float,
    L_FG: float,
    N: int,
) -> Tuple[complex | np.ndarray, ...]:
    """
    Calculate various impedance components of the Mesa and total impedance.
    """
    V_bottom = VOLTAGE_RATIO * V
    R_out = series_sum(R_ext, R_gnd, R_mid, R_FG)
    L_out = series_sum(L_ext, L_FG)
    Z_out = series_sum(R_out, 1j * V_bottom * L_out)

    Z_C = -1j / (V_bottom * C)
    Z_L = 1j * V_bottom * L
    Z_res = series_sum(R, Z_L, Z_C)

    Z_top = parallel_sum(
        series_sum(R_loss_t, -1j / (V_bottom * C_intt)),
        (1 - VOLTAGE_RATIO) * R_int,
    )
    Z_bottom = parallel_sum(
        series_sum(R_loss_b, -1j / (V_bottom * C_intb)),
        VOLTAGE_RATIO * R_int,
    )

    Z_tot = parallel_sum(
        Z_bottom,
        series_sum(Z_top, parallel_sum(Z_out, Z_res)),
    )

    return Z_C, Z_res, Z_top, Z_bottom, Z_out, Z_tot


def output_power(
    V: np.ndarray,
    R_int: np.ndarray,
    ratio: float,
    R: float,
    L: float,
    C: float,
    C_intt: float,
    C_intb: float,
    R_loss_t: float,
    R_loss_b: float,
    Ic: float,
    R_ext: float,
    L_ext: float,
    R_gnd: float,
    R_mid: float,
    R_FG: float,
    L_FG: float,
    N: int,
) -> np.ndarray:
    """
    Calculate the output power based on model parameters and input data.
    """
    Z_C, Z_res, Z_top, Z_bottom, Z_out, Z_tot = mesa_impedance(
        V,
        R_int,
        R,
        L,
        C,
        C_intt,
        C_intb,
        R_loss_t,
        R_loss_b,
        R_ext,
        L_ext,
        R_gnd,
        R_mid,
        R_FG,
        L_FG,
        N,
    )
    I_ext = Z_tot * Ic / series_sum(Z_top, parallel_sum(Z_out, Z_res))
    I_res = parallel_sum(Z_out, Z_res) * I_ext / Z_res
    power = R * np.abs(I_res) ** 2 / 2
    return ratio * power
