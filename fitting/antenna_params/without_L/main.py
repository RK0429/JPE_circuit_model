"""Command-line interface for antenna parameter fitting without inductive terms."""

from __future__ import annotations

import argparse
import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence

import lmfit as lf
import numpy as np
from lmfit.model import ModelResult
from numpy.typing import NDArray

from ..utils.fitting import perform_fitting, setup_fitting_model
from ..utils.io import load_data, load_txt_data
from ..utils.plot import (
    ComplexFigureData,
    FittingSeries,
    plot_complex_figure,
    plot_fitting_results,
    plot_txt_data,
)
from .model import CONSTANTS, output_power

constants = CONSTANTS

LOGGER = logging.getLogger(__name__)

FloatArray = NDArray[np.float64]


def build_parser() -> ArgumentParser:
    parser = argparse.ArgumentParser(description="Antenna parameter fitting (no inductance)")
    parser.add_argument("--bo-file", required=True, help="Bolometer output data path")
    parser.add_argument("--ive-file", required=True, help="IV experiment data path")
    parser.add_argument("--txt-file", required=True, help="Simulation sweep data path")
    parser.add_argument("--fig6", default="Fig6.pdf", help="Destination for fitting figure")
    parser.add_argument(
        "--fig10",
        default="Fig10.pdf",
        help="Destination for composite figure",
    )
    parser.add_argument(
        "--epsilon-fit",
        type=float,
        default=15_000.0,
        help="Scaling factor applied to bolometer data during fitting",
    )
    parser.add_argument(
        "--epsilon-comp",
        type=float,
        default=5_000.0,
        help="Scaling factor for the composite figure",
    )
    parser.add_argument(
        "--rrad",
        type=float,
        default=23.0,
        help="Radiation resistance used when plotting text data",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> Namespace:
    return build_parser().parse_args(argv)


def _initial_parameters() -> dict[str, float]:
    scale = constants.charge * 2.0 / constants.reduced_planck / 808.0
    return {
        "ratio": 1.0,
        "mesa_resistance": 55.04,
        "mesa_inductance": 3.27e-10 * scale,
        "mesa_capacitance": 2.748e-16 * scale,
        "top_capacitance": 4.339e-11 * scale,
        "bottom_capacitance": 3.222e-12 * scale,
        "top_loss_resistance": 0.202,
        "bottom_loss_resistance": 2.922,
        "bias_current": 18e-3,
        "external_resistance": 1.15,
        "external_inductance": 10e-9 * scale,
        "ground_resistance": 7.20,
        "middle_resistance": 8.29,
        "finger_resistance": 50.0,
        "finger_inductance": 10e-9 * scale,
    }


def _parameter_bounds() -> tuple[dict[str, float], dict[str, float]]:
    initial = _initial_parameters()
    lower = dict.fromkeys(initial, 0.0)
    upper = dict.fromkeys(initial, float(np.inf))
    return lower, upper


def _parameter_activity() -> dict[str, bool]:
    return {
        "ratio": False,
        "mesa_resistance": True,
        "mesa_inductance": True,
        "mesa_capacitance": True,
        "top_capacitance": False,
        "bottom_capacitance": False,
        "top_loss_resistance": False,
        "bottom_loss_resistance": False,
        "bias_current": False,
        "external_resistance": False,
        "external_inductance": False,
        "ground_resistance": False,
        "middle_resistance": False,
        "finger_resistance": False,
        "finger_inductance": False,
    }


def _configure_model() -> tuple[lf.Model, lf.Parameters]:
    model = setup_fitting_model(output_power)
    params = model.make_params()

    initial = _initial_parameters()
    lower, upper = _parameter_bounds()
    vary = _parameter_activity()

    for name in model.param_names:
        params[name].set(
            value=initial[name],
            min=lower[name],
            max=upper[name],
            vary=vary[name],
        )
    return model, params


def _scale_bolometer_output(values: FloatArray, epsilon: float) -> FloatArray:
    return values / constants.scaling_sb * epsilon


def _fit_model(
    voltage: FloatArray,
    internal_resistance: FloatArray,
    bolometer_scaled: FloatArray,
    weights: FloatArray,
) -> ModelResult:
    model, params = _configure_model()
    return perform_fitting(
        model=model,
        params=params,
        voltage=voltage,
        internal_resistance=internal_resistance,
        measured_power=bolometer_scaled,
        weights=weights,
    )


def _evaluate_model(
    voltage: FloatArray,
    internal_resistance: FloatArray,
    **parameters: float,
) -> FloatArray:
    return output_power(voltage, internal_resistance, **parameters)


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    bolometer_df, ive_df = load_data(args.bo_file, args.ive_file)
    internal_resistance = bolometer_df["Resistance"].to_numpy()
    bolometer_output = bolometer_df["Bolometer Output"].to_numpy() * 1e-3
    voltage = bolometer_df["Reduced Voltage"].to_numpy()

    macro_resistance = ive_df["Resistance"].to_numpy()
    macro_voltage = ive_df["Reduced Voltage"].to_numpy()
    macro_current = ive_df["Current"].to_numpy()
    macro_bolometer = ive_df["Bolometer Detection"].to_numpy() * 1e-3

    bolometer_scaled = _scale_bolometer_output(bolometer_output, args.epsilon_fit)
    result = _fit_model(voltage, internal_resistance, bolometer_scaled, bolometer_output)

    fitted_parameters: dict[str, float] = dict(result.best_values)
    fitted_parameters["mesa_inductance"] *= 2.0
    fitted_parameters["mesa_capacitance"] /= 2.1

    fitted_power = _evaluate_model(voltage, internal_resistance, **fitted_parameters)
    plot_fitting_results(
        experimental=FittingSeries(voltage=voltage, power=bolometer_scaled),
        calculated=FittingSeries(voltage=voltage, power=fitted_power),
        figure_path=args.fig6,
    )

    macro_power = _evaluate_model(macro_voltage, macro_resistance, **result.best_values)
    plot_fitting_results(
        experimental=FittingSeries(
            voltage=macro_voltage,
            power=_scale_bolometer_output(macro_bolometer, args.epsilon_fit),
        ),
        calculated=FittingSeries(voltage=macro_voltage, power=macro_power),
        figure_path=args.fig6,
    )

    sweep_df = load_txt_data(args.txt_file)
    plot_txt_data(
        dataframe=sweep_df,
        figure_path=args.fig10,
        epsilon=args.epsilon_comp,
        radiation_resistance=args.rrad,
    )

    voltage_calculated = (
        sweep_df["V(nt)"].to_numpy() - sweep_df["V(na)"].to_numpy()
    )
    current_calculated = -sweep_df["I(Rfg)"].to_numpy() * 1e3
    power_calculated = sweep_df["power"].to_numpy() * args.rrad

    plot_complex_figure(
        experimental=ComplexFigureData(
            voltage=macro_voltage,
            current=macro_current,
            power=macro_bolometer,
        ),
        calculated=ComplexFigureData(
            voltage=voltage_calculated,
            current=current_calculated,
            power=power_calculated,
        ),
        figure_path=args.fig10,
        constants=constants,
        epsilon=args.epsilon_comp,
        show_experimental=True,
    )


if __name__ == "__main__":
    main()
