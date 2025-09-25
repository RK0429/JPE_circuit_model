"""Internal resistance fitting utilities."""

from .fitting import perform_fitting
from .io import load_data, save_processed_data
from .model import (
    internal_resistance_from_temperature,
    temperature_from_power,
    thermal_resistance_from_temperature,
)
from .processing import process_data
from .solvers import (
    current_to_internal_voltage,
    internal_voltage_residual,
    temperature_residual,
)

__all__ = [
    "current_to_internal_voltage",
    "internal_resistance_from_temperature",
    "internal_voltage_residual",
    "load_data",
    "perform_fitting",
    "process_data",
    "save_processed_data",
    "temperature_from_power",
    "temperature_residual",
    "thermal_resistance_from_temperature",
]
