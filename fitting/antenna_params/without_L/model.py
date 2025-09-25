"""Antenna parameter fitting model without the inductive term."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

ComplexArray = NDArray[np.complex128]
RealArray = NDArray[np.float64]


@dataclass(frozen=True)
class PhysicalConstants:
    """Collection of physical constants used in the analysis."""

    planck: float = 6.626_070_15e-34  # Planck constant (J s)
    permeability: float = 1.256_637_062_12e-6  # Vacuum permeability (H/m)
    permittivity: float = 8.854_187_812_8e-12  # Vacuum permittivity (F/m)
    charge: float = 1.602_176_63e-19  # Elementary charge (C)
    scaling_sb: float = 1.75e5  # Empirical scaling constant

    @property
    def reduced_planck(self) -> float:
        return self.planck / (2.0 * np.pi)

    @property
    def Sb(self) -> float:  # noqa: N802
        return self.scaling_sb


CONSTANTS = PhysicalConstants()

VOLTAGE_RATIO: float = (43.0 + 159.0) / (15.0 + 43.0 + 159.0)


def series_sum(*impedances: complex | ComplexArray) -> complex | ComplexArray:
    """Return the sum of impedances connected in series."""
    if not impedances:
        return np.array([], dtype=complex)
    total = impedances[0]
    for impedance in impedances[1:]:
        total += impedance
    return total


def parallel_sum(*impedances: complex | ComplexArray) -> ComplexArray:
    """Return the equivalent impedance of impedances connected in parallel."""
    if not impedances:
        return np.array([], dtype=complex)
    susceptance = sum(1.0 / impedance for impedance in impedances)
    with np.errstate(divide="ignore", invalid="ignore"):
        total_impedance = np.where(susceptance != 0, 1.0 / susceptance, np.inf)
    return np.asarray(total_impedance, dtype=np.complex128)


def mesa_impedance(  # noqa: PLR0913
    voltage: RealArray,
    internal_resistance: RealArray,
    *,
    mesa_resistance: float,
    mesa_inductance: float,
    mesa_capacitance: float,
    top_capacitance: float,
    bottom_capacitance: float,
    top_loss_resistance: float,
    bottom_loss_resistance: float,
    external_resistance: float,
    external_inductance: float,
    ground_resistance: float,
    middle_resistance: float,
    finger_resistance: float,
    finger_inductance: float,
) -> tuple[ComplexArray, ComplexArray, ComplexArray, ComplexArray, ComplexArray, ComplexArray]:
    """Compute element impedances and the combined mesa impedance."""
    voltage_complex = np.asarray(voltage, dtype=np.complex128)
    internal_complex = np.asarray(internal_resistance, dtype=np.complex128)
    voltage_bottom = VOLTAGE_RATIO * voltage_complex
    outer_resistance = series_sum(external_resistance, ground_resistance, middle_resistance, finger_resistance)
    outer_inductance = series_sum(external_inductance, finger_inductance)
    outer_impedance = series_sum(outer_resistance, 1j * voltage_bottom * outer_inductance)

    capacitor_impedance = -1j / (voltage_bottom * mesa_capacitance)
    inductor_impedance = 1j * voltage_bottom * mesa_inductance
    resonator_impedance = series_sum(mesa_resistance, inductor_impedance, capacitor_impedance)

    top_impedance = parallel_sum(
        series_sum(top_loss_resistance, -1j / (voltage_bottom * top_capacitance)),
        (1.0 - VOLTAGE_RATIO) * internal_complex,
    )
    bottom_impedance = parallel_sum(
        series_sum(bottom_loss_resistance, -1j / (voltage_bottom * bottom_capacitance)),
        VOLTAGE_RATIO * internal_complex,
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


def output_power(  # noqa: PLR0913 - lmfit requires explicit parameter mapping
    voltage: RealArray,
    internal_resistance: RealArray,
    *,
    ratio: float,
    mesa_resistance: float,
    mesa_inductance: float,
    mesa_capacitance: float,
    top_capacitance: float,
    bottom_capacitance: float,
    top_loss_resistance: float,
    bottom_loss_resistance: float,
    bias_current: float,
    external_resistance: float,
    external_inductance: float,
    ground_resistance: float,
    middle_resistance: float,
    finger_resistance: float,
    finger_inductance: float,
) -> RealArray:
    """Return the radiated power predicted by the circuit model."""
    (
        _cap_impedance,
        resonator_impedance,
        top_impedance,
        _bottom_impedance,
        outer_impedance,
        total_impedance,
    ) = mesa_impedance(
        voltage,
        internal_resistance,
        mesa_resistance=mesa_resistance,
        mesa_inductance=mesa_inductance,
        mesa_capacitance=mesa_capacitance,
        top_capacitance=top_capacitance,
        bottom_capacitance=bottom_capacitance,
        top_loss_resistance=top_loss_resistance,
        bottom_loss_resistance=bottom_loss_resistance,
        external_resistance=external_resistance,
        external_inductance=external_inductance,
        ground_resistance=ground_resistance,
        middle_resistance=middle_resistance,
        finger_resistance=finger_resistance,
        finger_inductance=finger_inductance,
    )

    injection_current = total_impedance * bias_current / series_sum(
        top_impedance,
        parallel_sum(outer_impedance, resonator_impedance),
    )
    resonator_current = parallel_sum(outer_impedance, resonator_impedance) * injection_current / resonator_impedance
    power = mesa_resistance * np.abs(resonator_current) ** 2 / 2.0
    return ratio * np.asarray(power, dtype=np.float64)
