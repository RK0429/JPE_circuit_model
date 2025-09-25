"""Plotting helpers for the internal resistance fitting workflow."""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from lmfit.model import ModelResult
from numpy.typing import NDArray

from .model import thermal_resistance_from_temperature

LOGGER = logging.getLogger(__name__)

FloatArray = NDArray[np.float64]


def _save_figure(output: str | None, suffix: str = "") -> None:
    if output is None:
        plt.show()
        return

    path = Path(output)
    if suffix:
        path = path.with_name(f"{path.stem}_{suffix}{path.suffix}")
    plt.savefig(path)
    LOGGER.info("Plot saved to %s", path)
    plt.show()


def plot_thermal_resistance(result: ModelResult, output: str | None = None) -> None:
    """Plot thermal resistance as a function of temperature."""
    temperatures = np.linspace(-50.0, 100.0, 100)
    resistances = thermal_resistance_from_temperature(
        temperatures,
        result.best_values["alpha"],
        result.best_values["beta"],
        result.best_values["gamma"],
    )

    plt.figure(figsize=(8, 6))
    plt.plot(temperatures, resistances, label="Thermal resistance model")
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Thermal Resistance [K/W]")
    plt.xlabel("Temperature [K]")
    plt.legend()
    plt.tight_layout()
    _save_figure(output)


def plot_voltage_current(
    current_values: FloatArray,
    measured_voltage: FloatArray,
    model_voltage: FloatArray,
    output: str | None = None,
) -> None:
    """Plot the measured and modelled voltage against current."""
    plt.figure(figsize=(8, 6))
    plt.scatter(current_values * 1e3, measured_voltage, label="Measured", s=5)
    plt.scatter(current_values * 1e3, model_voltage, label="Model", s=5)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Voltage [V]")
    plt.xlabel("Current [mA]")
    plt.legend()
    plt.tight_layout()
    _save_figure(output)


def plot_current_temperature(
    current_values: FloatArray,
    temperature_values: FloatArray,
    output: str | None = None,
) -> None:
    """Plot the calculated temperature versus current."""
    plt.figure(figsize=(8, 6))
    plt.scatter(current_values, temperature_values, s=5)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Temperature [K]")
    plt.xlabel("Current [A]")
    plt.tight_layout()
    _save_figure(output, suffix="Temperature_vs_Current")


def plot_current_thermal_resistance(
    current_values: FloatArray,
    thermal_resistance_values: FloatArray,
    result: ModelResult,
    output: str | None = None,
) -> None:
    """Plot the thermal resistance versus current."""
    plt.figure(figsize=(8, 6))
    plt.scatter(current_values, thermal_resistance_values, s=5)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Thermal Resistance [K/W]")
    plt.xlabel("Current [A]")
    plt.ylim(0.0, result.best_values["gamma"] * 10.0)
    plt.tight_layout()
    _save_figure(output, suffix="Thermal_Resistance_vs_Current")
