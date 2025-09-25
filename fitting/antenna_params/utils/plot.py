"""Plotting helpers for antenna parameter analyses."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from numpy.typing import NDArray

LOGGER = logging.getLogger(__name__)

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class FittingSeries:
    """Voltage/power series used for the 1D fitting plots."""

    voltage: FloatArray
    power: FloatArray


@dataclass(frozen=True)
class FittingLabels:
    """Optional label overrides for the fitting plot."""

    experimental: str = "Experimental"
    calculated: str = "Calculated"
    xlabel: str = "Voltage [V]"
    ylabel: str = "Output Power [μW]"


@dataclass(frozen=True)
class ComplexFigureData:
    """Container for voltage, current, and power traces."""

    voltage: FloatArray
    current: FloatArray
    power: FloatArray


class SupportsSb(Protocol):
    """Protocol describing objects exposing the ``Sb`` scaling constant."""

    @property
    def Sb(self) -> float:  # noqa: N802
        ...


def _configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "Times New Roman",
            "mathtext.fontset": "cm",
            "mathtext.default": "it",
            "font.size": 15,
        }
    )


def plot_fitting_results(
    experimental: FittingSeries,
    calculated: FittingSeries,
    *,
    figure_path: str,
    labels: FittingLabels | None = None,
) -> None:
    """Plot experimental and calculated output power against voltage."""
    label_config = labels or FittingLabels()
    plt.figure(figsize=(8, 6))
    plt.scatter(
        experimental.voltage,
        experimental.power * 1e6,
        label=label_config.experimental,
        s=5,
    )
    plt.scatter(
        calculated.voltage,
        calculated.power * 1e6,
        label=label_config.calculated,
        s=5,
    )
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.legend()
    plt.xlabel(label_config.xlabel)
    plt.ylabel(label_config.ylabel)
    plt.tight_layout()
    plt.savefig(figure_path)
    LOGGER.info("Fitting results plot saved to %s", figure_path)
    plt.show()


def plot_complex_figure(
    experimental: ComplexFigureData,
    calculated: ComplexFigureData,
    *,
    figure_path: str,
    constants: SupportsSb,
    epsilon: float = 5000.0,
    show_experimental: bool = True,
) -> None:
    """Create a composite figure showing voltage, current, and power relationships."""
    _configure_style()

    figure = plt.figure(figsize=(8, 8))
    grid = GridSpec(ncols=2, nrows=2, width_ratios=[5, 2], height_ratios=[2, 5])

    axis_top = figure.add_subplot(grid[0])
    axis_side = figure.add_subplot(grid[3])
    axis_body = figure.add_subplot(grid[2], sharex=axis_top, sharey=axis_side)

    axis_top.grid(ls="--")
    if show_experimental:
        axis_top.scatter(
            experimental.voltage,
            experimental.power / constants.Sb * epsilon * 1e6,
            label="Experimental",
            s=5,
            c="gray",
        )
    axis_top.scatter(
        calculated.voltage,
        calculated.power * 1e6,
        s=5,
        c=calculated.power * 1e6,
        cmap="jet",
    )
    axis_top.set_ylabel("Output Power [μW]")
    axis_top.yaxis.set_label_coords(-0.1, 0.5)
    axis_top.set_xlim(-0.05, 1.5)

    axis_side.grid(ls="--")
    if show_experimental:
        axis_side.scatter(
            experimental.power / constants.Sb * epsilon * 1e6,
            experimental.current,
            label="Experimental",
            s=5,
            c="gray",
        )
    axis_side.scatter(
        calculated.power * 1e6,
        calculated.current,
        s=5,
        c=calculated.power * 1e6,
        cmap="jet",
    )
    axis_side.set_xlabel("Output Power [μW]")
    axis_side.set_ylim(0, 45)
    axis_side.set_yticks(np.arange(0, 50, 10))

    axis_body.grid(ls="--")
    if show_experimental:
        axis_body.scatter(experimental.voltage, experimental.current, s=5, c="gray")
    axis_body.scatter(
        calculated.voltage,
        calculated.current,
        s=5,
        c=calculated.power * 1e6,
        cmap="jet",
    )
    axis_body.set_xlabel("Voltage [V]")
    axis_body.set_ylabel("Current [mA]")
    axis_body.yaxis.set_label_coords(-0.1, 0.5)
    axis_body.set_xlim(-0.05, 1.5)
    axis_body.set_ylim(0, 45)
    axis_body.set_xticks(np.linspace(0, 1.25, 6))
    axis_body.set_yticks(np.arange(0, 50, 10))

    figure.tight_layout()
    plt.setp(axis_top.get_xticklabels(), visible=False)
    plt.setp(axis_side.get_yticklabels(), visible=False)
    plt.subplots_adjust(hspace=0.0, wspace=0.0)

    plt.savefig(figure_path)
    LOGGER.info("Complex figure saved to %s", figure_path)
    plt.show()


def plot_txt_data(
    dataframe: pd.DataFrame,
    *,
    figure_path: str,
    epsilon: float = 5000.0,
    radiation_resistance: float = 62.69,
    voltage_columns: Sequence[str] = ("V(nt)", "V(na)"),
    current_column: str = "I(Rfg)",
    power_column: str = "power",
) -> None:
    """Render a composite figure from the simulated text output."""
    _configure_style()

    figure = plt.figure(figsize=(8, 8))
    grid = GridSpec(ncols=2, nrows=2, width_ratios=[5, 2], height_ratios=[2, 5])

    axis_top = figure.add_subplot(grid[0])
    axis_side = figure.add_subplot(grid[3])
    axis_body = figure.add_subplot(grid[2], sharex=axis_top, sharey=axis_side)

    voltage_difference = dataframe[voltage_columns[0]].to_numpy() - dataframe[
        voltage_columns[1]
    ].to_numpy()
    scaled_power = (
        dataframe[power_column].to_numpy() * radiation_resistance * epsilon * 1e6
    )
    scaled_current = -dataframe[current_column].to_numpy() * 1e3

    axis_top.grid(ls="--")
    axis_top.scatter(
        voltage_difference,
        scaled_power,
        s=5,
        c=scaled_power,
        cmap="jet",
    )
    axis_top.set_xlim(-0.05, 1.5)
    axis_top.set_ylabel(r"Output Power [$μ$W]")
    axis_top.yaxis.set_label_coords(-0.1, 0.5)

    axis_side.grid(ls="--")
    axis_side.scatter(
        scaled_power,
        scaled_current,
        s=5,
        c=scaled_power,
        cmap="jet",
    )
    axis_side.set_xlabel(r"Output Power [$μ$W]")

    axis_body.grid(ls="--")
    axis_body.scatter(
        voltage_difference,
        scaled_current,
        s=5,
        c=scaled_power,
        cmap="jet",
    )
    axis_body.set_xlabel("Voltage [V]")
    axis_body.set_ylabel("Current [mA]")
    axis_body.set_xticks(np.linspace(0, 1.25, 6))
    axis_body.set_xlim(-0.05, 1.5)
    axis_body.yaxis.set_label_coords(-0.1, 0.5)

    figure.tight_layout()
    plt.setp(axis_top.get_xticklabels(), visible=False)
    plt.setp(axis_side.get_yticklabels(), visible=False)
    plt.subplots_adjust(hspace=0.0, wspace=0.0)

    plt.savefig(figure_path)
    LOGGER.info("Text data plot saved to %s", figure_path)
    plt.show()
