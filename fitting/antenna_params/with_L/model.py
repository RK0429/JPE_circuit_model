"""Antenna parameter fitting model including internal inductances."""

# ruff: noqa: N803

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

RealArray = NDArray[np.float64]
ComplexArray = NDArray[np.complex128]


@dataclass(frozen=True)
class PhysicalConstants:
    """Collection of physical constants used throughout the model."""

    e: float = 1.602_176_63e-19
    h: float = 6.626_070_15e-34
    mu_0: float = 1.256_637_062_12e-6
    epsilon_0: float = 8.854_187_812_8e-12
    Sb: float = 1.75e5

    @property
    def hbar(self) -> float:
        """Reduced Planck constant."""
        return self.h / (2.0 * np.pi)


constants = PhysicalConstants()

_DEFAULT_STACKS = 808
_DEFAULT_RATIO_NUMERATOR = 43.0 + 159.0
_DEFAULT_RATIO_DENOMINATOR = 15.0 + _DEFAULT_RATIO_NUMERATOR
_VOLTAGE_RATIO_BASE = _DEFAULT_RATIO_NUMERATOR / _DEFAULT_RATIO_DENOMINATOR

GAMMA = 2.0 * constants.e / constants.hbar / _DEFAULT_STACKS


class StackCountError(ValueError):
    """Raised when an invalid stack count is provided to the model."""

    def __init__(self, stack_count: int) -> None:
        message = f"stack_count must be positive (received {stack_count})"
        super().__init__(message)


def _voltage_ratio(stack_count: int) -> float:
    """Return the empirical bottom-voltage ratio for the given stack count."""
    if stack_count <= 0:
        raise StackCountError(stack_count)
    return _VOLTAGE_RATIO_BASE


def series_sum(*impedances: complex | ComplexArray) -> ComplexArray:
    if not impedances:
        return np.asarray([], dtype=np.complex128)
    total = np.asarray(impedances[0], dtype=np.complex128)
    for impedance in impedances[1:]:
        total += np.asarray(impedance, dtype=np.complex128)
    return total


def parallel_sum(*impedances: complex | ComplexArray) -> ComplexArray:
    if not impedances:
        return np.asarray([], dtype=np.complex128)
    admittance = sum(1.0 / np.asarray(impedance, dtype=np.complex128) for impedance in impedances)
    with np.errstate(divide="ignore", invalid="ignore"):
        total = np.where(admittance != 0.0, 1.0 / admittance, np.inf)
    return np.asarray(total, dtype=np.complex128)


def mesa_impedance(  # noqa: PLR0913
    voltage: RealArray,
    internal_resistance: RealArray,
    *,
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
    L_int_t: float,
    L_int_b: float,
) -> tuple[ComplexArray, ComplexArray, ComplexArray, ComplexArray, ComplexArray, ComplexArray]:
    bottom_ratio = _voltage_ratio(N)
    voltage_complex = np.asarray(voltage, dtype=np.complex128)
    internal_complex = np.asarray(internal_resistance, dtype=np.complex128)
    voltage_bottom = bottom_ratio * voltage_complex

    outer_resistance = series_sum(R_ext, R_gnd, R_mid, R_FG)
    outer_inductance = series_sum(L_ext, L_FG)
    outer_impedance = series_sum(outer_resistance, 1j * voltage_bottom * outer_inductance)

    capacitor_impedance = -1j / (voltage_bottom * C)
    inductor_impedance = 1j * voltage_bottom * L
    resonator_impedance = series_sum(R, inductor_impedance, capacitor_impedance)

    top_impedance = parallel_sum(
        series_sum(
            R_loss_t,
            1j * voltage_bottom * L_int_t,
            -1j / (voltage_bottom * C_intt),
        ),
        (1.0 - bottom_ratio) * internal_complex,
    )
    bottom_impedance = parallel_sum(
        series_sum(
            R_loss_b,
            1j * voltage_bottom * L_int_b,
            -1j / (voltage_bottom * C_intb),
        ),
        bottom_ratio * internal_complex,
    )

    total_impedance = parallel_sum(
        bottom_impedance,
        series_sum(top_impedance, parallel_sum(outer_impedance, resonator_impedance)),
    )

    components = (
        capacitor_impedance,
        resonator_impedance,
        top_impedance,
        bottom_impedance,
        outer_impedance,
        total_impedance,
    )
    return tuple(np.asarray(component, dtype=np.complex128) for component in components)  # type: ignore[return-value]


def output_power(  # noqa: PLR0913
    voltage: RealArray,
    internal_resistance: RealArray,
    *,
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
    L_int_t: float,
    L_int_b: float,
) -> RealArray:
    (
        _capacitor_impedance,
        resonator_impedance,
        top_impedance,
        _bottom_impedance,
        outer_impedance,
        total_impedance,
    ) = mesa_impedance(
        voltage,
        internal_resistance,
        R=R,
        L=L,
        C=C,
        C_intt=C_intt,
        C_intb=C_intb,
        R_loss_t=R_loss_t,
        R_loss_b=R_loss_b,
        R_ext=R_ext,
        L_ext=L_ext,
        R_gnd=R_gnd,
        R_mid=R_mid,
        R_FG=R_FG,
        L_FG=L_FG,
        N=N,
        L_int_t=L_int_t,
        L_int_b=L_int_b,
    )

    injection_current = total_impedance * Ic / series_sum(
        top_impedance,
        parallel_sum(outer_impedance, resonator_impedance),
    )
    resonator_current = (
        parallel_sum(outer_impedance, resonator_impedance)
        * injection_current
        / resonator_impedance
    )
    power = R * np.abs(resonator_current) ** 2 / 2.0
    return ratio * np.asarray(power, dtype=np.float64)
