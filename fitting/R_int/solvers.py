"""Numerical solvers used in the internal resistance fitting workflow."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import OptimizeResult, root

from .model import (
    internal_resistance_from_temperature,
    temperature_from_power,
    thermal_resistance_from_temperature,
)

LOGGER = logging.getLogger(__name__)

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ModelParameters:
    coeff_a: float
    coeff_b: float
    coeff_c: float
    coeff_d: float
    alpha: float
    beta: float
    gamma: float
    bath_temperature: float


def temperature_residual(
    temperature: float,
    *,
    power: float,
    parameters: ModelParameters,
) -> float:
    """Residual used to solve for the device temperature."""
    thermal_resistance = float(
        thermal_resistance_from_temperature(
            temperature,
            parameters.alpha,
            parameters.beta,
            parameters.gamma,
        )
    )
    predicted_temperature = float(
        temperature_from_power(
            power,
            thermal_resistance,
            parameters.bath_temperature,
        )
    )
    return temperature - predicted_temperature


def internal_voltage_residual(
    voltage: float,
    current: float,
    parameters: ModelParameters,
    *,
    temperature_solver: Callable[[float, ModelParameters], OptimizeResult] | None = None,
) -> float:
    """Residual used to solve for the internal voltage."""
    def _default_temperature_solver(
        power: float,
        model_parameters: ModelParameters,
    ) -> OptimizeResult:
        def _vector_residual(temp_vec: NDArray[np.float64]) -> NDArray[np.float64]:
            value = temperature_residual(
                float(temp_vec[0]),
                power=power,
                parameters=model_parameters,
            )
            return np.asarray([value], dtype=np.float64)

        return root(_vector_residual, x0=np.asarray([30.0], dtype=np.float64))

    solver = temperature_solver or _default_temperature_solver

    power = voltage * current
    solution = solver(power, parameters)

    if hasattr(solution, "success") and not solution.success:
        LOGGER.warning(
            "Temperature root finding did not converge for voltage=%s, current=%s",
            voltage,
            current,
        )

    temperature_value = float(solution.x[0])
    internal_resistance = float(
        internal_resistance_from_temperature(
            temperature_value,
            parameters.coeff_a,
            parameters.coeff_b,
            parameters.coeff_c,
            parameters.coeff_d,
        )
    )
    return voltage - internal_resistance * current


def current_to_internal_voltage(  # noqa: PLR0913 - lmfit requires explicit parameters
    currents: FloatArray,
    *,
    coeff_a: float,
    coeff_b: float,
    coeff_c: float,
    coeff_d: float,
    alpha: float,
    beta: float,
    gamma: float,
    bath_temperature: float,
) -> FloatArray:
    """Return the internal voltage corresponding to ``currents``."""
    voltages = np.empty_like(currents)
    parameters = ModelParameters(
        coeff_a=coeff_a,
        coeff_b=coeff_b,
        coeff_c=coeff_c,
        coeff_d=coeff_d,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
        bath_temperature=bath_temperature,
    )

    for index, current in enumerate(currents):
        def _voltage_residual_vector(
            volt_vec: NDArray[np.float64],
            current_value: float = current,
        ) -> NDArray[np.float64]:
            value = internal_voltage_residual(
                float(volt_vec[0]),
                current_value,
                parameters,
            )
            return np.asarray([value], dtype=np.float64)

        solution = root(
            _voltage_residual_vector,
            x0=np.asarray([20e-3], dtype=np.float64),
        )
        if solution.success:
            voltages[index] = solution.x[0]
        else:
            LOGGER.warning("Voltage root finding did not converge for current=%s", current)
            voltages[index] = np.nan
    return voltages
