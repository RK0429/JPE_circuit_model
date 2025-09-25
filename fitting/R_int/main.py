"""Command-line entry point for the internal resistance fitting workflow."""

from __future__ import annotations

import argparse
import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence

import lmfit as lf
import numpy as np
from lmfit.model import ModelResult
from numpy.typing import NDArray

from .fitting import perform_fitting
from .io import load_data, save_processed_data
from .model import (
    temperature_from_power,
    thermal_resistance_from_temperature,
)
from .plot import (
    plot_current_temperature,
    plot_current_thermal_resistance,
    plot_thermal_resistance,
    plot_voltage_current,
)
from .processing import process_data
from .solvers import current_to_internal_voltage

FloatArray = NDArray[np.float64]


def build_parser() -> ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal resistance fitting")
    parser.add_argument("input_file", help="Path to the raw data file")
    parser.add_argument(
        "--output-data",
        "-o",
        default="processed_data.dat",
        help="Destination path for the processed dataset",
    )
    parser.add_argument(
        "--output-plot",
        "-p",
        default="fit_plots.pdf",
        help="Destination path for the generated plots",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> Namespace:
    return build_parser().parse_args(argv)


def _initial_parameters() -> dict[str, float]:
    return {
        "coeff_a": 140.26315944091203,
        "coeff_b": 74.42877017162486,
        "coeff_c": 2993.7109475835937,
        "coeff_d": 14.966433685735403,
        "alpha": 0.0,
        "beta": 0.07007291353077101,
        "gamma": 7162.304320037531,
        "bath_temperature": -26.29469185418874,
    }


def _parameter_bounds() -> dict[str, tuple[float | None, float | None]]:
    return {
        "coeff_a": (0.0, None),
        "coeff_b": (0.0, 500.0),
        "coeff_c": (0.0, 10_000.0),
        "coeff_d": (0.0, None),
        "alpha": (0.0, 1.2),
        "beta": (0.005, 0.1),
        "gamma": (0.0, 8000.0),
        "bath_temperature": (-50.0, 40.0),
    }


def _parameter_activity() -> dict[str, bool]:
    return {
        "coeff_a": True,
        "coeff_b": True,
        "coeff_c": True,
        "coeff_d": True,
        "alpha": False,
        "beta": False,
        "gamma": True,
        "bath_temperature": True,
    }


def _configure_model() -> tuple[lf.Model, lf.Parameters]:
    model = lf.Model(
        current_to_internal_voltage,
        independent_vars=["currents"],
        param_names=[
            "coeff_a",
            "coeff_b",
            "coeff_c",
            "coeff_d",
            "alpha",
            "beta",
            "gamma",
            "bath_temperature",
        ],
    )
    params = model.make_params()

    initial = _initial_parameters()
    bounds = _parameter_bounds()
    vary = _parameter_activity()

    for name in model.param_names:
        parameter = params[name]
        lower, upper = bounds[name]
        parameter.set(
            value=initial[name],
            min=lower,
            max=upper,
            vary=vary[name],
        )

    return model, params


def _compute_calculated_values(
    currents: FloatArray,
    result: ModelResult,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    voltages = np.asarray(
        current_to_internal_voltage(currents, **result.best_values),
        dtype=np.float64,
    )
    power = voltages * currents
    temperatures = np.asarray(
        temperature_from_power(
            power,
            result.best_values["gamma"],
            result.best_values["bath_temperature"],
        ),
        dtype=np.float64,
    )
    thermal_resistance = np.asarray(
        thermal_resistance_from_temperature(
            temperatures,
            result.best_values["alpha"],
            result.best_values["beta"],
            result.best_values["gamma"],
        ),
        dtype=np.float64,
    )
    return voltages, temperatures, thermal_resistance


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    dataframe = load_data(args.input_file)
    processed = process_data(dataframe)
    save_processed_data(processed, args.output_data)

    currents = processed["Current"].to_numpy() * 1e-3
    voltages = processed["Reduced Voltage"].to_numpy()

    model, params = _configure_model()
    result = perform_fitting(model, params, currents, voltages)

    plot_thermal_resistance(result, output=args.output_plot)

    calc_voltages, temperatures, thermal_resistance = _compute_calculated_values(
        currents, result
    )
    plot_voltage_current(currents, voltages, calc_voltages, output=args.output_plot)

    plot_current_temperature(currents, temperatures, output=args.output_plot)
    plot_current_thermal_resistance(
        currents,
        thermal_resistance,
        result,
        output=args.output_plot,
    )


if __name__ == "__main__":
    main()
